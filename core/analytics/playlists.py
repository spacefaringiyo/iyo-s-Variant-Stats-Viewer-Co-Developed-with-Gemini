import json
import os
from pathlib import Path

# Expanded Playlist Paths
home = Path.home()
DEFAULT_PLAYLIST_PATHS = [
    # Windows
    Path("C:/Program Files (x86)/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists"),
    Path("D:/SteamLibrary/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists"),
    
    # Linux - Native
    home / ".steam/steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists",
    home / ".local/share/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists",
    
    # Linux - Flatpak
    home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists",
    home / ".var/app/com.valvesoftware.Steam/.steam/steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists",

    # Linux - Snap
    home / "snap/steam/common/.local/share/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists",

    # Linux - Custom Mounts
    Path("/mnt/Games/SteamLibrary/steamapps/common/FPSAimTrainer/FPSAimTrainer/Saved/SaveGames/Playlists"),
]

def auto_detect_playlists_path():
    """Returns the first valid playlist path found, or None."""
    for p in DEFAULT_PLAYLIST_PATHS:
        if p.exists() and p.is_dir():
            return str(p)
    return None

def scan_playlists(folder_path):
    """
    Scans a folder for .json files.
    Returns: List of dicts [{'name': 'Filename (No Ext)', 'path': 'Full Path'}]
    """
    if not folder_path: return []
    path = Path(folder_path)
    if not path.exists(): return []

    playlists = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.name.endswith('.json') and entry.is_file():
                    # Clean name: "My Playlist.json" -> "My Playlist"
                    name = entry.name[:-5]
                    playlists.append({
                        'name': name,
                        'path': entry.path,
                        'mtime': entry.stat().st_mtime
                    })
    except OSError:
        return []
    
    # Sort by Name
    playlists.sort(key=lambda x: x['name'].lower())
    return playlists

def parse_playlist(json_path):
    """
    Parses a KovaaK's Playlist JSON.
    Returns: List of Scenario Names (Strings).
    """
    try:
        # Use utf-8-sig to handle BOM if present
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            
        scenarios = []
        # Support both "Online" and "Offline" formats (structure is shared)
        if 'scenarioList' in data and isinstance(data['scenarioList'], list):
            for item in data['scenarioList']:
                if 'scenario_name' in item:
                    scenarios.append(item['scenario_name'])
        
        return scenarios
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error parsing playlist {json_path}: {e}")
        return []

def get_active_playlist(playlists_folder_path):
    """
    Checks for 'PlaylistInProgress.json' in the parent directory of the playlists folder.
    Returns: (Playlist Name, List of Scenarios) or (None, [])
    """
    if not playlists_folder_path: return None, []
    
    # Path logic: Playlists are in .../Saved/SaveGames/Playlists
    # InProgress is in .../Saved/SaveGames/PlaylistInProgress.json
    try:
        pl_path = Path(playlists_folder_path)
        parent_dir = pl_path.parent
        active_file = parent_dir / "PlaylistInProgress.json"
        
        if active_file.exists():
            # KEY FIX: Use 'utf-8-sig' to handle Byte Order Mark (BOM)
            with open(active_file, 'r', encoding='utf-8-sig') as f:
                content = f.read().strip()
                if not content: return None, [] # Handle empty file check
                data = json.loads(content)
                
            name = data.get('playlistName', 'Unknown Playlist')
            # Handle user's specific whitespace case just to be safe
            name = name.strip() 
            
            scenarios = []
            if 'scenarioList' in data:
                for item in data['scenarioList']:
                    if 'scenario_name' in item:
                        scenarios.append(item['scenario_name'])
            
            return name, scenarios
            
    except Exception as e:
        # If it fails (e.g. file locked by KovaaKs), just return None silently-ish
        # print(f"Debug - Active PL Error: {e}") 
        pass
        
    return None, []