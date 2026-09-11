
"""
Application Settings with Pydantic
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration"""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    workers: int = 1  # Use 1 worker for development (avoids Prometheus metrics conflicts)
    
    # Supabase Configuration (REQUIRED)
    # Supports both VITE_ prefixed (from frontend) and direct names
    supabase_url: str = ""
    supabase_key: str = ""  # Service role key for backend operations
    supabase_anon_key: str = ""  # Anon key for client verification
    
    # Support for VITE_ prefixed variables (from frontend .env)
    vite_supabase_url: str = ""
    vite_supabase_anon_key: str = ""
    vite_supabase_service_key: str = ""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Use VITE_ prefixed if direct names not provided
        if not self.supabase_url and self.vite_supabase_url:
            self.supabase_url = self.vite_supabase_url
        if not self.supabase_anon_key and self.vite_supabase_anon_key:
            self.supabase_anon_key = self.vite_supabase_anon_key
        if not self.supabase_key and self.vite_supabase_service_key:
            self.supabase_key = self.vite_supabase_service_key
        
        # Local mode needs nothing but a DeepSeek key: no database, no cloud
        # storage, no auth. Everything lives on disk and in memory.
        if not self.local_mode:
            if not self.supabase_url:
                raise ValueError("SUPABASE_URL or VITE_SUPABASE_URL is required")
            if not self.supabase_key:
                raise ValueError("SUPABASE_KEY or VITE_SUPABASE_SERVICE_KEY is required")
            if not self.supabase_anon_key:
                raise ValueError("SUPABASE_ANON_KEY or VITE_SUPABASE_ANON_KEY is required")
        if not self.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required in .env file")

    # Game engine
    # "godot" = generate a Godot 4 project, validate it in the engine and export
    #           a playable web build (needs the Godot binary + export templates)
    # "html5" = the single-file HTML5 Canvas path
    game_engine: str = "godot"
    godot_path: str = "godot"
    godot_projects_dir: str = "./godot_projects"
    godot_repair_rounds: int = 3

    # Local mode
    # True  = no Supabase, no database, no auth. Games are written to disk and
    #         served by this backend. Project state is in memory and is lost on
    #         restart. For local testing of game generation only.
    # False = the normal Supabase-backed path.
    local_mode: bool = False

    # Where this backend is reachable from the browser. Used to build preview
    # URLs in local mode.
    public_base_url: str = "http://localhost:8000"

    # Directory for locally stored game files (local mode only).
    local_storage_dir: str = "./local_storage"

    # Auth
    # When False, every request runs as a fixed local dev user and no token is
    # required. Intended for focused local work on generation. Defaults to True
    # so that forgetting to set it can never open a deployment up.
    auth_enabled: bool = True

    # Storage
    storage_bucket: str = "gamoraai-projects"
    
    # AI API Keys (REQUIRED)
    # Loads from DEEPSEEK_API_KEY environment variable in .env file
    deepseek_api_key: str

    # DeepSeek model configuration.
    # deepseek-flash = DeepSeek-V4.1-Flash: 1M context, 384K max output, and
    # per DeepSeek's own docs it "comprehensively surpassed V4 Pro". Thinking
    # mode is a request parameter now, not a separate model.
    deepseek_model: str = "deepseek-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_thinking: bool = True
    deepseek_reasoning_effort: str = "high"
    
    # Projects
    projects_dir: str = "./projects"
    
    # Monitoring (Optional)
    sentry_dsn: str = ""
    
    # AI Asset Generation (Optional - defaults to False)
    enable_ai_assets: bool = False  # DALL-E disabled - DeepSeek used for descriptions only
    ai_asset_tier: str = "premium"  # Minimum tier to use AI assets (free/premium/pro)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields like VITE_* variables
