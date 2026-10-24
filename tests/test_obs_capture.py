import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[1]

def png(width,height,color):
    def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    rows=b''.join(b'\0'+bytes(v for x in range(width) for v in color(x,y)) for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')

class NativeCapture(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT/'tools/verify_obs_capture.py').is_file(),'native artifact acceptance gate missing')
        spec=importlib.util.spec_from_file_location('verify_obs_capture',ROOT/'tools/verify_obs_capture.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)
        self.master=ROOT/'assets/branding/StreamStrike-logo.png'
        (self.out/'resource.png').write_bytes(self.master.read_bytes())
        idle=self.master.read_bytes()
        for p in ['application-icon.png','window-icon.png','tray-icon.png']:(self.out/p).write_bytes(idle)
        (self.out/'state-active.png').write_bytes(png(1024,1024,lambda x,y:(200,20,30,255)))
        (self.out/'state-paused.png').write_bytes(png(1024,1024,lambda x,y:(240,170,20,255)))
        (self.out/'native.png').write_bytes(png(800,500,lambda x,y:(x%256,y%256,(x+y)%256,255)))
        self.runtime={'status':'captured','kind':'native-window-framebuffer','platform':'xcb','title':'StreamStrike - OBS 33.0.0-streamstrike',
         'width':800,'height':500,'resourceSHA256':'86acca5004fbe90a471230159b452d3eb4a3663db30dac5d26523f43f470d926',
         'nativeWindowId':'123','captureMethod':'QScreen::grabWindow(root,frameGeometry)','captureRegion':[0,0,800,500],
         'trayAvailable':True,'trayVisible':True,'iconStateProof':'actual-tray-object-presentation-only','capturedUTC':'2026-10-24T00:00:00.000Z'}
        self.build={'donor_commit':'72e86655715d9a25d69ce446aa4dd44ba58e10d2','overlay_sha256':'a'*64,'source_inventory_sha256':'b'*64,'executable_sha256':'c'*64,'runtime_inventory_sha256':'e'*64,'runtime_report_sha256':'f'*64}
        self.build['capture_nonce']='d'*32
        self.runtime['captureNonce']=self.build['capture_nonce']
        self.runtime['executableSHA256']=self.build['executable_sha256']
        identity={k:v for k,v in self.build.items() if k!='capture_nonce'}
        self.runtime['buildIdentitySHA256']=self.m.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode())
        pixels={'width':16,'height':16,'nonTransparentPixels':48,'rgbaSHA256':'1'*64}
        self.runtime['uiIconReadiness']={'svgImageReader':True,'originalSvgResource':':/res/images/plus.svg',
            'originalSvgSHA256':'559bbcc914d0ee4a4c61f2af615f4cfac4100f90f93ac2de0b8a9cf3a4af9891',
            'originalSvgPixmap':dict(pixels),'toolbarButtons':{
                name:{**pixels,'visible':True,'enabled':True,'alphaMatchesOriginal':True}
                for name in ('scenesToolbar/actionAddScene','sourcesToolbar/actionAddSource')}}
        self.bind_artifacts()

    def bind_artifacts(self):
        self.runtime['artifactSHA256']={p.name:self.m.sha256(p.read_bytes()) for p in self.out.glob('*.png')}
        self.save()
    def save(self): (self.out/'runtime.json').write_text(json.dumps(self.runtime))
    def check(self): return self.m.validate_capture(self.out,self.master,self.build)
    def test_complete_capture_metadata_and_pixels_are_indexed(self):
        result=self.check();self.assertEqual(result['build'],self.build);self.assertEqual(result['files']['native.png']['dimensions'],[800,500])
        self.assertIn('native.png',result['files'])
    def test_missing_window_icon_rejected(self):
        (self.out/'window-icon.png').unlink()
        with self.assertRaises(OSError):self.check()
    def test_capture_failure_cannot_be_reported_as_success(self):
        (self.out/'failure.json').write_text('{}')
        with self.assertRaises(ValueError):self.check()
    def test_wrong_compiled_resource_rejected(self):
        (self.out/'resource.png').write_bytes(png(8,8,lambda x,y:(0,0,0,0)))
        with self.assertRaisesRegex(ValueError,'resource'):self.check()
    def test_window_icon_not_matching_application_rejected(self):
        (self.out/'window-icon.png').write_bytes((self.out/'state-active.png').read_bytes());self.bind_artifacts()
        with self.assertRaisesRegex(ValueError,'icon'):self.check()
    def test_identical_status_states_rejected(self):
        (self.out/'state-active.png').write_bytes((self.out/'state-paused.png').read_bytes());self.bind_artifacts()
        with self.assertRaisesRegex(ValueError,'state'):self.check()
    def test_blank_native_image_rejected(self):
        (self.out/'native.png').write_bytes(png(800,500,lambda x,y:(50,50,50,255)));self.bind_artifacts()
        with self.assertRaisesRegex(ValueError,'detail'):self.check()
    def test_reconstructed_or_offscreen_image_rejected(self):
        self.runtime['platform']='offscreen';self.save()
        with self.assertRaisesRegex(ValueError,'native'):self.check()
    def test_absent_actual_tray_rejected(self):
        self.runtime['trayAvailable']=False;self.save()
        with self.assertRaisesRegex(ValueError,'tray'):self.check()
    def test_wrong_dimensions_rejected(self):
        self.runtime['width']=1000;self.save()
        with self.assertRaisesRegex(ValueError,'dimensions'):self.check()
    def test_wrong_donor_rejected(self):
        self.build['donor_commit']='0'*40
        with self.assertRaisesRegex(ValueError,'donor'):self.check()
    def test_stale_capture_nonce_rejected(self):
        self.build['capture_nonce']='e'*32
        with self.assertRaisesRegex(ValueError,'nonce'):self.check()
    def test_changed_expected_executable_rejected(self):
        self.build['executable_sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'executable'):self.check()
    def test_changed_expected_overlay_rejected(self):
        self.build['overlay_sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'build identity'):self.check()
    def test_swapped_native_file_rejected(self):
        (self.out/'native.png').write_bytes(png(800,500,lambda x,y:(y%256,x%256,(x+y)%256,255)))
        with self.assertRaisesRegex(ValueError,'artifact'):self.check()
    def test_missing_artifact_manifest_rejected(self):
        del self.runtime['artifactSHA256'];self.save()
        with self.assertRaisesRegex(ValueError,'artifact'):self.check()
    def test_runtime_inventory_report_is_bound_to_build_and_binary(self):
        report={'version':1,'inventory':{'version':1,'files':{'bin/obs':{'sha256':self.build['executable_sha256']}}},'elf':{'bin/obs':{'needed':[]}}}
        self.build['runtime_inventory_sha256']=self.m.sha256(json.dumps(report['inventory'],sort_keys=True,separators=(',',':')).encode())
        self.build['runtime_report_sha256']=self.m.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode())
        self.m.validate_runtime_report(report,self.build)
        report['inventory']['files']['bin/obs']['sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'inventory'):self.m.validate_runtime_report(report,self.build)
    def test_tampered_closure_report_rejected_with_unchanged_inventory(self):
        report={'version':1,'inventory':{'version':1,'files':{'bin/obs':{'sha256':self.build['executable_sha256']}}},'elf':{'bin/obs':{'needed':[],'runpath':[]}}}
        self.build['runtime_inventory_sha256']=self.m.sha256(json.dumps(report['inventory'],sort_keys=True,separators=(',',':')).encode())
        self.build['runtime_report_sha256']=self.m.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode())
        self.m.validate_runtime_report(report,self.build)
        report['elf']['bin/obs']['runpath']=['/unrelated']
        with self.assertRaisesRegex(ValueError,'report'):self.m.validate_runtime_report(report,self.build)
    def test_empty_runtime_dependency_report_rejected(self):
        with self.assertRaisesRegex(ValueError,'ELF'):self.m.validate_runtime_report({'version':1,'elf':{}},self.build)
    def test_png_crc_corruption_rejected(self):
        p=self.out/'native.png';b=bytearray(p.read_bytes());b[40]^=1;p.write_bytes(b)
        with self.assertRaisesRegex(ValueError,'PNG'):self.check()
    def test_missing_original_ui_icon_readiness_rejected(self):
        del self.runtime['uiIconReadiness'];self.save()
        with self.assertRaisesRegex(ValueError,'SVG|toolbar'):self.check()
    def test_missing_svg_handler_or_wrong_source_rejected(self):
        original=json.loads(json.dumps(self.runtime['uiIconReadiness']))
        for key,value in [('svgImageReader',False),('originalSvgResource',':/invented.svg'),('originalSvgSHA256','0'*64)]:
            self.runtime['uiIconReadiness']={**original,key:value};self.save()
            with self.assertRaisesRegex(ValueError,'SVG|toolbar'):self.check()
    def test_missing_hidden_disabled_or_blank_actual_toolbar_icon_rejected(self):
        original=json.loads(json.dumps(self.runtime['uiIconReadiness']))
        for key,value in [('visible',False),('enabled',False),('nonTransparentPixels',0),('rgbaSHA256','bad'),('width',0),('alphaMatchesOriginal',False)]:
            self.runtime['uiIconReadiness']=json.loads(json.dumps(original))
            self.runtime['uiIconReadiness']['toolbarButtons']['scenesToolbar/actionAddScene'][key]=value;self.save()
            with self.assertRaisesRegex(ValueError,'SVG|toolbar'):self.check()
        self.runtime['uiIconReadiness']=original
        del self.runtime['uiIconReadiness']['toolbarButtons']['sourcesToolbar/actionAddSource'];self.save()
        with self.assertRaisesRegex(ValueError,'SVG|toolbar'):self.check()

if __name__=='__main__':unittest.main()
