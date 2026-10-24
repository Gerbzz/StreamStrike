"""Validate real-frontend artifacts; source/runtime review remains a separate gate."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

PIN='72e86655715d9a25d69ce446aa4dd44ba58e10d2'
MASTER='86acca5004fbe90a471230159b452d3eb4a3663db30dac5d26523f43f470d926'


def sha256(data): return hashlib.sha256(data).hexdigest()


def decode_png(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('invalid PNG signature')
    offset=8; compressed=bytearray(); header=None; ended=False
    while offset<len(data):
        if offset+12>len(data): raise ValueError('truncated PNG')
        length=struct.unpack_from('>I',data,offset)[0];kind=data[offset+4:offset+8]
        end=offset+12+length
        if end>len(data): raise ValueError('truncated PNG chunk')
        body=data[offset+8:offset+8+length]
        if zlib.crc32(kind+body)&0xffffffff != struct.unpack_from('>I',data,offset+8+length)[0]:raise ValueError('PNG CRC mismatch')
        if kind==b'IHDR':
            if header or offset!=8 or length!=13:raise ValueError('invalid PNG header')
            header=struct.unpack('>IIBBBBB',body)
        elif kind==b'IDAT':compressed.extend(body)
        elif kind==b'IEND':
            ended=True
            if length or end!=len(data):raise ValueError('PNG trailing data')
            break
        offset=end
    if not header or not ended:raise ValueError('incomplete PNG')
    width,height,depth,color,compression,filtering,interlace=header
    if not(0<width<=8192 and 0<height<=8192) or depth!=8 or color not in (2,6) or compression or filtering or interlace:
        raise ValueError('unsupported PNG layout')
    bpp=3 if color==2 else 4;stride=width*bpp;expected=(stride+1)*height
    if expected>64*1024*1024:raise ValueError('PNG pixel budget exceeded')
    dec=zlib.decompressobj();raw=dec.decompress(bytes(compressed),expected+1)
    if len(raw)!=expected or not dec.eof or dec.unused_data or dec.unconsumed_tail:raise ValueError('PNG decompressed length mismatch')
    rgba=bytearray();previous=bytearray(stride)
    def paeth(a,b,c):
        p=a+b-c;pa=abs(p-a);pb=abs(p-b);pc=abs(p-c)
        return a if pa<=pb and pa<=pc else b if pb<=pc else c
    for y in range(height):
        f=raw[y*(stride+1)];row=bytearray(raw[y*(stride+1)+1:(y+1)*(stride+1)])
        if f>4:raise ValueError('unsupported PNG filter')
        if f:
            for x in range(stride):
                left=row[x-bpp] if x>=bpp else 0;up=previous[x];corner=previous[x-bpp] if x>=bpp else 0
                row[x]=(row[x]+(left if f==1 else up if f==2 else (left+up)//2 if f==3 else paeth(left,up,corner)))&255
        if bpp==4:rgba.extend(row)
        else:
            for x in range(0,stride,3):rgba.extend(row[x:x+3]+b'\xff')
        previous=row
    return width,height,bytes(rgba)


def matches_master(pixels, master):
    width,height,rgba=pixels;mw,mh,mrgba=master
    if width!=height or width<16 or width>1024:return False
    if any(rgba[i+3] for i in [0,(width-1)*4,(height-1)*width*4,(width*height-1)*4]):return False
    checked=0
    for gy in range(2,62):
        for gx in range(2,62):
            mx=int((gx+.5)*mw/64);my=int((gy+.5)*mh/64)
            offset=(my*mw+mx)*4;want=mrgba[offset:offset+4]
            if want[3]!=255:continue
            # Compare only solid interiors, avoiding renderer-dependent edge interpolation.
            if any(mrgba[((my+dy)*mw+mx+dx)*4:((my+dy)*mw+mx+dx)*4+4]!=want for dx,dy in [(-8,0),(8,0),(0,-8),(0,8)]):continue
            x=int((gx+.5)*width/64);y=int((gy+.5)*height/64);got=rgba[(y*width+x)*4:(y*width+x)*4+4]
            if any(abs(a-b)>4 for a,b in zip(got,want)):return False
            checked+=1
    return checked>=64


def validate_capture(folder, master_path, build):
    folder=Path(folder);master_data=Path(master_path).read_bytes()
    if sha256(master_data)!=MASTER:raise ValueError('master resource does not match published identity')
    if build.get('donor_commit')!=PIN:raise ValueError('wrong donor pin')
    if any(not re.fullmatch('[a-f0-9]{64}',build.get(k,'')) for k in ['overlay_sha256','source_inventory_sha256','executable_sha256','runtime_inventory_sha256','runtime_report_sha256']):raise ValueError('invalid build identity')
    if (folder/'failure.json').exists():raise ValueError('runtime reported failed capture')
    runtime=json.loads((folder/'runtime.json').read_text())
    if runtime.get('status')!='captured' or runtime.get('kind')!='native-window-framebuffer' or runtime.get('platform')!='xcb' or runtime.get('captureMethod')!='QScreen::grabWindow(root,frameGeometry)':raise ValueError('not the expected native capture method')
    if not runtime.get('title','').startswith('StreamStrike - OBS '):raise ValueError('wrong actual window title')
    if runtime.get('trayAvailable') is not True or runtime.get('trayVisible') is not True or runtime.get('iconStateProof')!='actual-tray-object-presentation-only':raise ValueError('actual tray state evidence missing')
    if not runtime.get('nativeWindowId','').isdigit() or int(runtime['nativeWindowId'])==0:raise ValueError('native window identity missing')
    nonce=build.get('capture_nonce','')
    if not re.fullmatch('[a-f0-9]{32}',nonce) or runtime.get('captureNonce')!=nonce:raise ValueError('capture nonce differs from fresh launch')
    if runtime.get('executableSHA256')!=build['executable_sha256']:raise ValueError('actual executable identity differs from verified build')
    identity={k:build[k] for k in ['donor_commit','overlay_sha256','source_inventory_sha256','executable_sha256','runtime_inventory_sha256','runtime_report_sha256']}
    identity_hash=sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode())
    if runtime.get('buildIdentitySHA256')!=identity_hash:raise ValueError('runtime build identity differs from expected source/overlay')
    resource=(folder/'resource.png').read_bytes()
    if resource!=master_data or runtime.get('resourceSHA256')!=MASTER:raise ValueError('compiled resource differs from master')
    names=['resource.png','application-icon.png','window-icon.png','tray-icon.png','state-active.png','state-paused.png','native.png']
    images={};files={}
    for name in names:
        data=(folder/name).read_bytes();pixels=decode_png(data);images[name]=pixels
        files[name]={'sha256':sha256(data),'bytes':len(data),'dimensions':list(pixels[:2]),'decoded_rgba_sha256':sha256(pixels[2])}
    if runtime.get('artifactSHA256')!={name:entry['sha256'] for name,entry in files.items()}:raise ValueError('runtime artifact hashes differ from saved files')
    idle=images['application-icon.png']
    if idle!=images['window-icon.png'] or idle!=images['tray-icon.png'] or not matches_master(idle,images['resource.png']):raise ValueError('actual application/window/tray icon mismatch')
    active=images['state-active.png'];paused=images['state-paused.png']
    if active[:2]!=idle[:2] or paused[:2]!=idle[:2] or active==paused or active==idle or paused==idle:raise ValueError('tray state distinction missing')
    native=images['native.png'];width,height,rgba=native
    if width<800 or height<500 or [width,height]!=[runtime.get('width'),runtime.get('height')] or runtime.get('captureRegion',[0,0,0,0])[2:]!=[width,height]:raise ValueError('native dimensions mismatch')
    colors=set(rgba[i:i+4] for i in range(0,len(rgba),4))
    if len(colors)<150:raise ValueError('native framebuffer lacks expected UI detail')
    return {'scope':'Actual OBS Linux frontend identity and synthetic native window only; not recording, streaming or other OS acceptance.',
            'build':build,'runtime':runtime,'files':files,'native_unique_colors':len(colors)}


def validate_runtime_report(report, build):
    inventory=report.get('inventory',{})
    if report.get('version')!=1 or not report.get('elf') or 'bin/obs' not in report['elf']:
        raise ValueError('installed ELF dependency report missing')
    if sha256(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode())!=build.get('runtime_inventory_sha256'):
        raise ValueError('installed runtime inventory differs from build receipt')
    if inventory.get('files',{}).get('bin/obs',{}).get('sha256')!=build.get('executable_sha256'):
        raise ValueError('installed runtime executable differs from build receipt')
    if sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode())!=build.get('runtime_report_sha256'):
        raise ValueError('installed runtime closure report differs from build receipt')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--build-evidence',required=True,type=Path)
    parser.add_argument('--runtime-evidence',required=True,type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    build=json.loads(args.build_evidence.read_text())
    runtime=validate_runtime_report(json.loads(args.runtime_evidence.read_text()),build)
    result=validate_capture(args.directory,root/'assets/branding/StreamStrike-logo.png',build)
    result['runtime_dependency_report_sha256']=sha256(args.runtime_evidence.read_bytes())
    result['installed_elf_count']=len(runtime['elf'])
    out=args.directory/'verified.json'
    with out.open('x') as file:json.dump(result,file,indent=2);file.write('\n')
    print('Verified fresh-launch build/artifact identity consistency; hosted process provenance and visual review still required.')

if __name__=='__main__':main()
