def load_config(guild_id):
    config_path = os.path.join(CONFIG_DIR, f"{guild_id}.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {"randomlyMessage": False, "responseFrequency": 4, "listen": True, "dumb": False, "mailTrusted": [], "mailChannel": None, "autoSearch": False, "greet": True, "announcements": True}

def save_config(guild_id, config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config_path = os.path.join(CONFIG_DIR, f"{guild_id}.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
