# AI Podcast Production Suite

An intelligent, multi-agent system for automated podcast content creation using Google ADK and LangGraph frameworks with Agent-to-Agent (A2A) communication.

## Overview

The AI Podcast Production Suite is a hybrid agentic system that combines Google's Agent Development Kit (ADK) and LangGraph to create a complete podcast production pipeline. The system uses 8 specialized agents that communicate via structured messages to transform a simple topic into a complete podcast package including script, show notes, and social media content.

### Key Features

- **Hybrid Agent Architecture**: Combines Google ADK and LangGraph agents in a single workflow
- **Agent-to-Agent Communication**: Structured message passing between agents using A2A protocol
- **MCP Tool Integration**: External tool access via Model Context Protocol (web search, audio tools)
- **Web Frontend** 🎨 NEW: Beautiful Streamlit interface - no command line needed!
- **Dialogue Simulation** 💬 NEW: Convert scripts to host-guest conversations for practice/polishing!
- **Enhanced Research** ✨ NEW: YouTube transcript extraction, academic paper search (arXiv, PubMed)
- **Parallel Execution** ⚡ NEW: 3-5x faster research with concurrent task execution
- **Citation System** 📚 NEW: Automatic academic citations in APA, MLA, Chicago formats
- **Structured Outputs**: Pydantic-validated data models ensure type safety throughout the pipeline
- **Dual Execution Modes**: Run in-process for development or A2A mode for distributed execution
- **Comprehensive Monitoring**: Callback system tracks agent execution, errors, and state changes
- **Production-Ready Exports**: Generates Markdown scripts, show notes, and JSON metadata

## Architecture

### Agent Pipeline

The system uses 8 specialized agents in a sequential pipeline:

1. **TopicRefinementAgent** (Google ADK) - Refines and expands the initial topic
2. **EnhancedTopicResearcherAgent** (Google ADK) ✨ - Multi-source research (Web, YouTube, Academic) with parallel execution
3. **OutlineArchitectAgent** (LangGraph) - Creates structured episode outline
4. **ScriptWriterAgent** (LangGraph) - Generates full podcast script
5. **FactCheckingValidatorAgent** - Validates claims and sources
6. **ShowNotesSpecialistAgent** - Creates comprehensive show notes
7. **SocialMediaCoordinatorAgent** - Generates social media posts
8. **ContentPackageCriticAgent** - Reviews and scores final package

### Framework Integration

#### Google ADK Agents

Google ADK agents inherit from `BaseADKAgent` and use the official `google-adk` package:

```python
from agents.base_adk_agent import BaseADKAgent
from google.genai import Client

class TopicRefinementAgent(BaseADKAgent):
    def __init__(self, gemini_client: Client):
        super().__init__(gemini_client=gemini_client, name="TopicRefinementAgent")
    
    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        # Agent logic using Gemini API
        response = self.gemini_client.models.generate_content(...)
        state.selected_refined_topic = response.text
        return state
```

#### LangGraph Agents

LangGraph agents inherit from `BaseLangGraphAgent` and use StateGraph for workflow definition:

```python
from agents.base_langgraph_agent import BaseLangGraphAgent
from langgraph.graph import StateGraph, END

class OutlineArchitectAgent(BaseLangGraphAgent):
    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        graph.add_node("extract_research", self._extract_research_node)
        graph.add_node("generate_outline", self._generate_outline_node)
        graph.add_edge("extract_research", "generate_outline")
        graph.add_edge("generate_outline", END)
        return graph.compile()
```

### A2A Communication

Agents communicate via structured messages using the A2A protocol:

```python
# Message structure
{
    "type": "state_update",
    "payload": {
        "initial_topic": "AI in Healthcare",
        "selected_refined_topic": "Beyond the Robot Doctor...",
        "research_materials": [...],
        # ... full PodcastProductionState
    },
    "next": "researcher"  # Optional routing hint
}
```

The `ADKAgentWrapper` and `LangGraphAgentWrapper` classes handle message serialization/deserialization and broker integration, enabling seamless cross-framework communication.

### Agent Registry

The `AgentRegistry` class provides centralized agent management:

```python
from agents import AgentRegistry
from config.settings import get_gemini_client

# Define pipeline order
pipeline_order = ["refinement", "researcher", "outline_architect", ...]

# Create registry
registry = AgentRegistry(
    pipeline_order=pipeline_order,
    gemini_client=get_gemini_client(),
    callback=callback_instance
)

# Register agents
registry.register_adk_agent("refinement", TopicRefinementAgent)
registry.register_langgraph_agent("outline_architect", OutlineArchitectAgent)

# Build all agents and wrappers
result = registry.build_all()
agents = result['agents']  # For in-process mode
wrapped_agents = result['all_wrapped']  # For A2A mode
```

## Installation

### Prerequisites

- Python 3.9 or higher
- Google Gemini API key
- Serper API key (for web search)
- `uv` package manager (for MCP servers)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd PodcastProduction-Assistant1
```

2. Create and activate virtual environment:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install `uv` for MCP server management:
```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh
```

5. Configure environment variables:
```bash
# Copy the example environment file
copy .env.example .env
# Edit .env with your API keys (use your preferred text editor)
notepad .env
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```properties
# Google Gemini Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Serper API Configuration (for web search)
SERPER_API_KEY=your_serper_api_key_here
WEB_SEARCH_ENGINE=google
SEARCH_RESULTS_COUNT=5
SEARCH_LANGUAGE=en
SEARCH_COUNTRY=us

# Application Settings
APP_NAME=Podcast Production Suite
LOG_LEVEL=INFO
MAX_RESEARCH_ITEMS=5
MAX_SOCIAL_POSTS=3

# Audio Settings
WORDS_PER_MINUTE=150

# YouTube API (Optional - for video search)
YOUTUBE_API_KEY=your_youtube_api_key_here
```

### Enhanced Research Features ✨

The system now includes enhanced research capabilities:

- **YouTube Transcript Extraction**: Automatically extracts transcripts from relevant YouTube videos
- **Academic Paper Search**: Searches arXiv and PubMed for scholarly sources
- **Parallel Execution**: All research tasks run simultaneously for 3-5x speed improvement

**Note:** YouTube transcript extraction works without an API key. The `YOUTUBE_API_KEY` is only needed for searching YouTube videos by topic.

To get a YouTube API key:
1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Enable "YouTube Data API v3"
3. Create an API key
4. Add to your `.env` file

See `ENHANCED_FEATURES.md` for detailed documentation.
```

### MCP Server Configuration

MCP servers are configured in `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "uvx",
      "args": ["mcp-server-fetch"],
      "env": {
        "SERPER_API_KEY": "${SERPER_API_KEY}"
      },
      "disabled": false,
      "autoApprove": ["web_search"]
    },
    "audio-tools": {
      "command": "python",
      "args": ["-m", "tools.audio_calculator_mcp_server"],
      "env": {},
      "disabled": false,
      "autoApprove": ["audio_duration_calculator"]
    }
  }
}
```

**Configuration Options:**
- `command`: Executable to run the MCP server
- `args`: Command-line arguments
- `env`: Environment variables (supports `${VAR}` substitution from .env)
- `disabled`: Set to `true` to disable the server
- `autoApprove`: List of tool names to auto-approve without user confirmation

## Usage

### Web Interface (Recommended) 🎨

Launch the beautiful Streamlit web interface:

```bash
streamlit run app.py
```

Then open your browser to `http://localhost:8501` and:
1. Enter your podcast topic
2. Choose tone and settings
3. Click "Generate Podcast"
4. View and download results!

**Features:**
- No command line needed
- Real-time progress tracking
- Interactive results dashboard
- One-click downloads
- Mobile-friendly

See `FRONTEND_GUIDE.md` for complete documentation.

### Command Line Interface

Run the pipeline with enhanced research (default):

```bash
python main.py "AI in Healthcare"
```

This automatically includes:
- Web search via MCP
- YouTube transcript extraction
- Academic paper search (arXiv + PubMed)
- Parallel execution for faster results

With options:

```bash
python main.py "AI in Healthcare" \
  --tone conversational \
  --log-level DEBUG \
  --cleanup
```

### A2A Mode (Distributed Execution)

Run with Agent-to-Agent communication via message broker:

```bash
python main.py "AI in Healthcare" \
  --a2a \
  --a2a-timeout 120
```

### Basic Research Mode

To use the original web-only research (without YouTube and academic sources):

```bash
python main.py "AI in Healthcare" --basic-research
```

### Command-Line Options

```
positional arguments:
  topic                 Main topic for the podcast episode

optional arguments:
  --tone {conversational,formal,humorous,technical,storytelling}
                        Tone for the podcast content (default: conversational)
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Logging level (default: INFO)
  --basic-research      Use basic research mode (web only, no YouTube/academic)
                        Default: Enhanced research with all sources
  --cleanup             Clean up old output directories before starting
  --a2a                 Use A2A mode with message broker
  --a2a-timeout SECONDS Timeout for A2A mode (default: 60)
  --strict              Fail early if required environment variables are missing
```

### Output

The system generates a complete podcast package in `output/<topic>/`:

```
output/
└── AI_in_Healthcare_20241109_143022/
    ├── script.md              # Full podcast script
    ├── show_notes.md          # Episode show notes
    ├── social_posts.json      # Social media content
    ├── metadata.json          # Episode metadata
    └── podcast_package.json   # Complete package (consolidated)
```

## Development

### Project Structure

```
PodcastProduction-Assistant1/
│
├── agents/                           # 🤖 Agent Implementations
│   ├── __init__.py                   # Agent exports
│   ├── base_adk_agent.py             # Base class for Google ADK agents
│   ├── base_langgraph_agent.py       # Base class for LangGraph agents
│   ├── registry.py                   # Unified agent registry & management
│   ├── topic_refinement_agent.py     # Refines user topics into podcast angles
│   ├── topic_researcher_agent.py     # Basic web research agent
│   ├── enhanced_researcher_agent.py  # Multi-source parallel research (Web + YouTube + Academic)
│   ├── outline_architect_agent.py    # Creates structured episode outlines
│   ├── script_writer_agent.py        # Generates full podcast scripts
│   ├── fact_checking_validator_agent.py  # Validates claims against sources
│   ├── show_notes_specialist_agent.py    # Creates comprehensive show notes
│   ├── social_media_coordinator_agent.py # Generates platform-specific posts
│   └── content_package_critic_agent.py   # Reviews and scores final package
│
├── adk_adapter/                      # 🔌 Google ADK Integration
│   ├── __init__.py
│   ├── adapter.py                    # ADKAgentWrapper for A2A communication
│   ├── a2a_message.py                # Message serialization/deserialization
│   └── run_adk_app.py                # ADK application runner
│
├── langgraph_adapter/                # 🔌 LangGraph Integration
│   ├── __init__.py
│   └── adapter.py                    # LangGraphAgentWrapper for A2A communication
│
├── a2a_broker/                       # 📨 Agent-to-Agent Message Broker
│   ├── __init__.py
│   ├── __main__.py                   # Broker entry point
│   └── broker.py                     # Pub/sub broker implementation
│
├── schemas/                          # 📋 Pydantic Data Models
│   ├── __init__.py
│   ├── state_models.py               # PodcastProductionState, FactCheckReport, etc.
│   └── output_models.py              # PodcastContentPackage, Metadata, etc.
│
├── tools/                            # 🛠️ MCP Tools & External Integrations
│   ├── __init__.py
│   ├── mcp_client.py                 # Main MCP client (entry point)
│   ├── mcp_client_http.py            # HTTP MCP client wrapper with fallback
│   ├── mcp_client_sync.py            # Synchronous MCP client
│   ├── web_search_mcp.py             # Web search tool (Serper API)
│   ├── audio_calculator_mcp.py       # Audio duration calculator
│   ├── youtube_transcript_tool.py    # YouTube transcript extraction
│   ├── academic_search_tool.py       # arXiv & PubMed search
│   ├── citation_manager.py           # Citation tracking & formatting
│   └── dialogue_simulator.py         # Script-to-dialogue conversion
│
├── mcp_servers/                      # 🌐 HTTP MCP Servers
│   ├── __init__.py
│   ├── http_mcp_client.py            # Low-level HTTP client for MCP servers
│   ├── web_search_http_server.py     # HTTP server for web search
│   └── audio_calculator_http_server.py # HTTP server for audio tools
│
├── callbacks/                        # 📊 Monitoring & Logging
│   ├── __init__.py
│   └── logging_callback.py           # PodcastProductionCallback implementation
│
├── config/                           # ⚙️ Configuration
│   ├── __init__.py
│   ├── settings.py                   # Environment & settings management
│   ├── constants.py                  # Application constants
│   └── retry_config.py               # Retry strategy configuration
│
├── utils/                            # 🔧 Utility Functions
│   ├── __init__.py
│   ├── file_writer.py                # File export utilities
│   ├── state_helpers.py              # State validation & helpers
│   ├── retry_handler.py              # Retry logic with backoff
│   ├── validation_utils.py           # Input validation utilities
│   ├── llm_helpers.py                # LLM interaction helpers
│   └── pydantic_compat.py            # Pydantic compatibility layer
│
├── output/                           # 📁 Generated Podcast Packages (gitignored)
│   └── <topic_name>/
│       ├── script.md
│       ├── show_notes.md
│       ├── social_posts.json
│       ├── metadata.json
│       └── podcast_package.json
│
├── .kiro/                            # 🔧 Kiro IDE Configuration
│   └── settings/
│       └── mcp.json                  # MCP server configuration
│
├── app.py                            # 🎨 Streamlit Web Interface
├── main.py                           # 🚀 CLI Application Entry Point
├── start_mcp_servers.py              # 🌐 MCP Server Launcher
├── requirements.txt                  # 📦 Python Dependencies
├── .env.example                      # 🔐 Environment Variables Template
├── .gitignore                        # Git ignore rules
└── README.md                         # 📖 This file
```

### Adding New Agents

#### Google ADK Agent

1. Create agent class inheriting from `BaseADKAgent`:

```python
from agents.base_adk_agent import BaseADKAgent
from schemas.state_models import PodcastProductionState

class MyNewAgent(BaseADKAgent):
    def __init__(self, gemini_client):
        super().__init__(gemini_client=gemini_client, name="MyNewAgent")
    
    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        # Implement agent logic
        return state
```

2. Register in `main.py`:

```python
registry.register_adk_agent("my_new_agent", MyNewAgent)
```

#### LangGraph Agent

1. Create agent class inheriting from `BaseLangGraphAgent`:

```python
from agents.base_langgraph_agent import BaseLangGraphAgent
from langgraph.graph import StateGraph, END

class MyLangGraphAgent(BaseLangGraphAgent):
    def __init__(self):
        super().__init__(name="MyLangGraphAgent")
    
    def _build_graph(self) -> StateGraph:
        graph = StateGraph(dict)
        # Define nodes and edges
        return graph.compile()
```

2. Register in `main.py`:

```python
registry.register_langgraph_agent("my_langgraph_agent", MyLangGraphAgent)
```

### Testing

Run tests:

```bash
# Test MCP connection
python test_mcp_connection.py

# Test A2A mode
python test_a2a_mode.py

# Test exports
python test_export.py

# Test validation
python test_validation.py
```

## Troubleshooting

### Common Issues

#### 1. Google ADK Import Errors

**Problem**: `ImportError: cannot import name 'Agent' from 'google.adk.agents'`

**Solution**:
```bash
pip install --upgrade google-adk
# Verify installation
python -c "from google.adk.agents import Agent; print('OK')"
```

#### 2. MCP Server Connection Failures

**Problem**: `MCPConnectionError: Failed to connect to web-search server`

**Solutions**:
- Verify `uv` is installed: `uv --version`
- Check MCP configuration in `.kiro/settings/mcp.json`
- Verify API keys in `.env` file
- Test MCP connection: `python test_mcp_connection.py`
- Check server logs for errors

#### 3. A2A Timeout Errors

**Problem**: `TimeoutError: Timed out waiting for final package after 60 seconds`

**Solutions**:
- Increase timeout: `--a2a-timeout 180`
- Check broker logs for agent failures
- Verify all agents are registered with broker
- Run in in-process mode for debugging: remove `--a2a` flag

#### 4. Gemini API Rate Limits

**Problem**: `429 Too Many Requests` from Gemini API

**Solutions**:
- Add delays between agent executions
- Use a higher-tier API key
- Implement exponential backoff in agent code
- Switch to a different model: `GEMINI_MODEL=gemini-1.5-pro`

#### 5. Missing Environment Variables

**Problem**: `KeyError: 'GEMINI_API_KEY'`

**Solutions**:
- Verify `.env` file exists and contains required variables
- Use `--strict` flag to fail early on missing variables
- Check environment variable names match exactly (case-sensitive)

#### 6. Pydantic Validation Errors

**Problem**: `ValidationError: 1 validation error for PodcastProductionState`

**Solutions**:
- Check agent output matches expected schema
- Review Pydantic model definitions in `schemas/state_models.py`
- Enable DEBUG logging to see full state: `--log-level DEBUG`
- Verify all required fields are populated

#### 7. LangGraph Checkpointing Issues

**Problem**: `CheckpointError: Failed to save checkpoint`

**Solutions**:
- Ensure write permissions in working directory
- Check disk space availability
- Verify LangGraph version: `pip show langgraph`
- Clear checkpoint directory if corrupted

### Debug Mode

Enable detailed logging:

```bash
python main.py "Your Topic" --log-level DEBUG
```

This will show:
- Agent execution flow
- State transitions
- Tool calls and responses
- Broker message routing
- Validation results

### Getting Help

If you encounter issues not covered here:

1. Check the logs in `--log-level DEBUG` mode
2. Review the agent execution flow
3. Test individual components (MCP, agents, broker)
4. Verify all dependencies are installed correctly
5. Check API key validity and quotas





