use std::{collections::HashSet, fs, path::PathBuf};

#[test]
#[ignore = "requires an actual app-produced native PNG from the capture job"]
fn native_editor_png_has_rendered_detail() {
    let path = PathBuf::from(std::env::var_os("STREAMSTRIKE_NATIVE_CAPTURE_PATH")
        .expect("native capture path must be set"));
    let bytes = fs::read(&path).expect("native capture PNG must exist");
    assert!((10_000..=5 * 1024 * 1024).contains(&bytes.len()), "unexpected PNG byte size");
    assert!(bytes.starts_with(b"\x89PNG\r\n\x1a\n"), "native capture must be PNG");
    let rgba = image::load_from_memory_with_format(&bytes, image::ImageFormat::Png)
        .expect("native capture must decode")
        .to_rgba8();
    let (width, height) = rgba.dimensions();
    assert!(width >= 900 && height >= 500, "native image too small: {width}x{height}");
    let mut colors = HashSet::new();
    for x in (40..width).step_by(47) {
        for y in (40..height).step_by(47) {
            colors.insert(rgba.get_pixel(x, y).0);
        }
    }
    assert!(colors.len() >= 8, "native image lacks rendered detail: {} colors", colors.len());
    println!("Native editor PNG {width}x{height}, {} sampled colors", colors.len());
}
