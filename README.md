# Gamora AI

Gamora AI is an intelligent game generation platform that leverages advanced AI to transform natural language prompts into fully playable web games. The platform automatically generates complete game code using HTML5 Canvas for 2D games and Three.js for 3D games, enabling users to create interactive games without writing a single line of code. Powered by DeepSeek AI, Gamora AI analyzes user intent, generates optimized game mechanics, and produces production-ready game code with real-time preview capabilities.

## Features

- **AI-Powered Game Generation**: Transform natural language descriptions into complete, playable games
- **2D and 3D Support**: Automatic dimension detection with HTML5 Canvas for 2D games and Three.js for 3D games
- **Real-Time Preview**: Live game preview with WebSocket-based progress updates
- **Cloud Storage**: Integrated Supabase storage for game assets and project management
- **User Authentication**: Secure user management with Supabase Auth
- **Project Management**: Track and manage multiple game projects with build history
- **Code Validation**: Automatic code validation and error correction with AI-powered fixes

## Tech Stack

### Backend
- **FastAPI**: High-performance async web framework
- **Python 3.12+**: Core backend language
- **DeepSeek API**: AI model for code generation (`deepseek-flash` / DeepSeek-V4.1-Flash)
- **Supabase**: PostgreSQL database, authentication, and storage
- **Redis**: Caching layer for improved performance
- **WebSockets**: Real-time communication for generation progress
- **Uvicorn**: ASGI server

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type-safe development
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Utility-first styling
- **Radix UI**: Accessible component primitives
- **React Router**: Client-side routing
- **TanStack Query**: Data fetching and caching

### Game Technologies
- **HTML5 Canvas**: 2D game rendering
- **Matter.js**: 2D physics engine
- **Three.js**: 3D graphics and rendering

## Prerequisites

- Python 3.12 or higher
- Node.js 18 or higher
- npm or yarn
- Supabase account and project
- DeepSeek API key

## Installation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd core
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the `core` directory:
```env
DEEPSEEK_API_KEY=your_deepseek_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_key
SUPABASE_ANON_KEY=your_supabase_anon_key
STORAGE_BUCKET=gamoraai-projects
```

5. Run the backend server:
```bash
python main.py
```

The backend will start on `http://localhost:8000`

### Frontend Setup

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file in the root directory:
```env
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

3. Start the development server:
```bash
npm run dev
```

The frontend will start on `http://localhost:8080`

## Project Structure

```
gamora/
├── core/                    # Backend Python application
│   ├── agents/             # AI agent implementations
│   ├── api/                # API route handlers
│   ├── config/             # Configuration management
│   ├── core/               # Core orchestration logic
│   ├── models/             # AI client models
│   ├── services/            # Business logic services
│   ├── utils/              # Utility functions
│   └── main.py             # Application entry point
├── src/                     # Frontend React application
│   ├── components/         # React components
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # Utility libraries
│   ├── pages/              # Page components
│   └── main.tsx            # Frontend entry point
└── web_templates/          # Game templates
```

## API Documentation

Once the backend is running, API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Running Tests

```bash
# Backend tests
cd core
pytest

# Frontend tests
npm test
```

### Building for Production

```bash
# Frontend build
npm run build

# Backend deployment
# Use uvicorn with production settings
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Environment Variables

### Backend (.env in core/)
- `DEEPSEEK_API_KEY`: Required - DeepSeek API key for AI generation
- `DEEPSEEK_MODEL`: Optional - model ID (default: `deepseek-flash`). The legacy
  `deepseek-chat` and `deepseek-reasoner` names were retired on 2026-07-24 and
  no longer resolve.
- `DEEPSEEK_BASE_URL`: Optional - API base URL (default: `https://api.deepseek.com`)
- `SUPABASE_URL`: Required - Supabase project URL
- `SUPABASE_KEY`: Required - Supabase service role key
- `SUPABASE_ANON_KEY`: Required - Supabase anonymous key
- `STORAGE_BUCKET`: Optional - Storage bucket name (default: gamoraai-projects)
- `SENTRY_DSN`: Optional - Sentry error tracking DSN

### Frontend (.env in root/)
- `VITE_SUPABASE_URL`: Required - Supabase project URL
- `VITE_SUPABASE_ANON_KEY`: Required - Supabase anonymous key

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For issues, questions, or contributions, please open an issue on the GitHub repository.

