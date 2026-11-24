# Utilities for discovering/loading cloud providers.
# Configure cloud providers via .env

_DEFAULT_CLOUD_MODELS = {
    "ollama": "gemma4:31b",
    "groq": "qwen/qwen3.8-27b",
    "pollinations": "meta/llama-3.3-70b-instruct",
}

def _env_value(*names):
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None

def _normalize_provider_name(name):
    return str(name).strip()

def _provider_from_name(name, index=0):
    name = _normalize_provider_name(name)
    if not name:
        return None
    keyname = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    if not keyname:
        return None
    url = _env_value(
        f"{keyname}_URL",
        f"{keyname}_API_URL",
        f"{keyname}_ENDPOINT",
        f"{keyname}_BASE_URL",
        f"LLM_{keyname}_URL",
        f"LLM_{keyname}_PROXY_URL",
        f"LLM_PROXY_URL_{keyname}",
    )
    key = _env_value(
        f"{keyname}_KEY",
        f"{keyname}_API_KEY",
        f"{keyname}_TOKEN",
        f"LLM_{keyname}_KEY",
        f"LLM_KEY_{keyname}",
    )
    model = _env_value(
        f"{keyname}_MODEL",
        f"{keyname}_DEFAULT_MODEL",
        f"LLM_{keyname}_MODEL",
        f"LLM_MODEL_{keyname}",
    )
    priority_raw = _env_value(f"{keyname}_PRIORITY")
    priority = None
    if priority_raw is not None:
        try:
            priority = int(priority_raw)
        except ValueError:
            priority = None
    if model is None:
        model = _DEFAULT_CLOUD_MODELS.get(name.lower())
    if not url or not key:
        return None
    return {
        "name": name,
        "url": url,
        "key": key,
        "model": model,
        "priority": priority if priority is not None else index,
        "_index": index,
    }

def _load_numbered_providers():
    providers = []
    index = 0
    i = 1
    while i <= 100:
        found = False
        for prefix in ("CLOUD_PROVIDER", "LLM_PROVIDER", "CLOUD"):
            url = _env_value(
                f"{prefix}_{i}_URL",
                f"{prefix}_{i}_API_URL",
                f"{prefix}_{i}_ENDPOINT",
                f"{prefix}_{i}_BASE_URL",
            )
            key = _env_value(
                f"{prefix}_{i}_KEY",
                f"{prefix}_{i}_API_KEY",
                f"{prefix}_{i}_TOKEN",
            )
            if url and key:
                found = True
                name = _env_value(f"{prefix}_{i}_NAME", f"{prefix}_{i}_ID") or f"{prefix.lower()}-{i}"
                model = _env_value(f"{prefix}_{i}_MODEL", f"{prefix}_{i}_DEFAULT_MODEL")
                priority_raw = _env_value(f"{prefix}_{i}_PRIORITY")
                priority = None
                if priority_raw is not None:
                    try:
                        priority = int(priority_raw)
                    except ValueError:
                        priority = None
                if model is None:
                    model = _DEFAULT_CLOUD_MODELS.get(str(name).lower())
                providers.append({
                    "name": name,
                    "url": url,
                    "key": key,
                    "model": model,
                    "priority": priority if priority is not None else index,
                    "_index": index,
                })
                index += 1
                break
        if not found:
            break
        i += 1
    return providers

def load_cloud_providers():
    providers = []

    raw = _env_value("CLOUD_PROVIDERS", "LLM_PROVIDERS", "CLOUD_PROVIDER_LIST")
    if raw is not None:
        parsed = None
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            parsed = None

        if isinstance(parsed, list):
            if parsed and all(isinstance(item, dict) for item in parsed):
                for idx, item in enumerate(parsed):
                    name = item.get("name") or item.get("id") or item.get("provider") or f"provider-{idx + 1}"
                    url = (item.get("url") or item.get("api_url")
                           or item.get("endpoint") or item.get("base_url"))
                    key = (item.get("key") or item.get("api_key")
                           or item.get("token"))
                    model = (item.get("model") or item.get("default_model"))
                    priority = item.get("priority", idx)
                    try:
                        priority = int(priority)
                    except (TypeError, ValueError):
                        priority = idx
                    if url and key:
                        if model is None:
                            model = _DEFAULT_CLOUD_MODELS.get(str(name).lower())
                        providers.append({
                            "name": name,
                            "url": url,
                            "key": key,
                            "model": model,
                            "priority": priority,
                            "_index": idx,
                        })
            else:
                for idx, item in enumerate(parsed):
                    if isinstance(item, str):
                        p = _provider_from_name(item, idx)
                        if p is not None:
                            providers.append(p)
        else:
            for idx, token in enumerate(re.split(r"[,\s]+", raw)):
                token = token.strip()
                if not token:
                    continue
                p = _provider_from_name(token, idx)
                if p is not None:
                    providers.append(p)

    if not providers:
        providers.extend(_load_numbered_providers())

    if not providers:
        url = _env_value("LLM_PROXY_URL")
        key = _env_value("LLM_KEY")
        model = _env_value("LLM_MODEL", "CLOUD_MODEL")
        if url and key:
            if model is None:
                model = _DEFAULT_CLOUD_MODELS.get("groq")
            providers.append({
                "name": "default",
                "url": url,
                "key": key,
                "model": model,
                "priority": 0,
                "_index": 0,
            })

    providers.sort(key=lambda p: (p.get("priority", p.get("_index", 0)), p.get("_index", 0)))
    for p in providers:
        p.pop("_index", None)
    return providers

# Backwards/alternative friendly aliases
get_cloud_providers = load_cloud_providers
get_available_cloud_providers = load_cloud_providers
_get_cloud_providers = load_cloud_providers
