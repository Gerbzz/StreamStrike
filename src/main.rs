use std::path::Path;
use streamstrike::storage::{create, load, save};
use streamstrike::{Project, SourceKind};

fn main() {
    match run(std::env::args().skip(1).collect()) {
        Ok(message) => println!("{message}"),
        Err(message) => {
            eprintln!("StreamStrike: {message}");
            std::process::exit(1);
        }
    }
}

fn run(args: Vec<String>) -> Result<String, String> {
    let Some(command) = args.first().map(String::as_str) else {
        return Err(usage());
    };
    match (command, args.len()) {
        ("new", 2) => {
            let path = Path::new(&args[1]);
            create(path, &Project::new())?;
            Ok(format!("created {} with Scene 1 (ID 1)", path.display()))
        }
        ("show", 2) => {
            let project = load(Path::new(&args[1]))?;
            serde_json::to_string_pretty(&project).map_err(|error| error.to_string())
        }
        ("add-scene", 3) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            let id = project.add_scene(&args[2])?;
            save(path, &project)?;
            Ok(format!("added scene ID {id}"))
        }
        ("select-scene", 3) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            project.select_scene(parse_id(&args[2])?)?;
            save(path, &project)?;
            Ok(format!("active scene ID {}", project.active_scene_id))
        }
        ("add-source", 6) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            let scene_id = parse_id(&args[2])?;
            let kind = SourceKind::parse(&args[4])
                .ok_or("kind must be display, window, microphone, or desktop_audio")?;
            let id = project.add_source(scene_id, &args[3], kind, &args[5])?;
            save(path, &project)?;
            Ok(format!(
                "added source ID {id}; selector is stored but not opened"
            ))
        }
        ("set-audio", 5) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            let id = parse_id(&args[2])?;
            let muted = args[3]
                .parse::<bool>()
                .map_err(|_| "mute must be true or false")?;
            let gain_db = args[4]
                .parse::<f32>()
                .map_err(|_| "gain must be a number in dB")?;
            project.set_audio(id, muted, gain_db)?;
            save(path, &project)?;
            Ok(format!(
                "stored audio settings for source ID {id}; no audio device is opened"
            ))
        }
        _ => Err(usage()),
    }
}

fn parse_id(text: &str) -> Result<u64, String> {
    let id = text
        .parse::<u64>()
        .map_err(|_| "ID must be a positive integer")?;
    if id == 0 {
        return Err("ID must be a positive integer".into());
    }
    Ok(id)
}

fn usage() -> String {
    "StreamStrike (source-only project CLI)\nby PWDS\nusage:\n  streamstrike new PATH.streamstrike\n  streamstrike show PATH.streamstrike\n  streamstrike add-scene PATH.streamstrike NAME\n  streamstrike select-scene PATH.streamstrike SCENE_ID\n  streamstrike add-source PATH.streamstrike SCENE_ID NAME KIND SELECTOR\n  streamstrike set-audio PATH.streamstrike SOURCE_ID true|false GAIN_DB\nKIND: display | window | microphone | desktop_audio".into()
}

