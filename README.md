# Cetacean-Aware Logistics Router

**AI-Powered Maritime Routing that Balances Logistics Efficiency with Marine Conservation**

## Overview

The Cetacean-Aware Logistics Router is a multi-agent AI system that calculates optimal shipping routes while minimizing the risk of ship strikes with endangered whales. The system uses:

- **3 Specialized AI Agents** (Navigator, Marine Biologist, Risk Manager)
- **LangGraph** for agent orchestration
- **Groq LLMs** for intelligent decision-making
- **MCP Servers** for real-time marine biology data (OBIS)
- **FastAPI** for REST API access

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                     │
│                                                           │
│  ┌───────────┐      ┌────────────┐      ┌──────────────┐  │
│  │ Navigator │─────▶│ Biologist  │─────▶│ Risk Manager │  │
│  │  Agent    │      │   Agent    │      │    Agent     │  │
│  └───────────┘      └────────────┘      └──────────────┘  │
│       │                    │                     │        │
│       └────────────────────┴─────────────────────┘        │
│                            │                              │
└────────────────────────────┼──────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │   MCP Servers   │
                    ├─────────────────┤
                    │ • OBIS Biology  │
                    │ • Route Calc    │
                    └─────────────────┘
```

### Agent Responsibilities

1. **Navigator Agent** - Calculates route options (direct, detour, reduced speed)
2. **Biologist Agent** - Assesses ecological risk using OBIS marine mammal data
3. **Risk Manager Agent** - Mediates between efficiency and safety, makes final decision

## Installation

### Prerequisites

- Python 3.9+
- Groq API key (get from [console.groq.com](https://console.groq.com))

### Setup

1. **Clone or create project directory:**
```bash
mkdir cetacean-router
cd cetacean-router
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and add your Groq API key
```

4. **Verify installation:**
```bash
python -c "import groq, langgraph, fastmcp, pyobis; print('All dependencies installed!')"
```

## Usage

### Command Line Interface

Run the main script for interactive examples:

```bash
python main.py
```

Options:
- **Option 1**: California to Oregon (Blue Whale Migration Route)
- **Option 2**: Transatlantic Route (NY to Portugal)
- **Option 3**: Pacific Route (LA to Honolulu)
- **Option 4**: Custom Route (enter your own coordinates)
- **Option 5**: Run all examples
- **Option 6**: Start API server

### REST API

Start the FastAPI server:

```bash
python -m api.main
# or from menu: select option 6
```

API will be available at `http://localhost:8000`

#### API Endpoints

**Health Check:**
```bash
curl http://localhost:8000/
```

**Optimize Route:**
```bash
curl -X POST http://localhost:8000/optimize-route \\
  -H "Content-Type: application/json" \\
  -d '{
    "start": {"latitude": 34.0, "longitude": -120.0},
    "end": {"latitude": 37.0, "longitude": -122.0},
    "max_iterations": 3
  }'
```

**Interactive API Docs:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Programmatic Usage

```python
from config.settings import settings
from graph.routing_graph import run_routing_optimization
from mcp_servers.obis_server import check_species_risk
from mcp_servers.route_calc_server import calculate_route_metrics

# Define route
start = (34.42, -119.70)  # Santa Barbara
end = (45.52, -122.68)     # Portland

# Run optimization
result = run_routing_optimization(
    start=start,
    end=end,
    obis_tool=check_species_risk,
    route_calc_tool=calculate_route_metrics,
    max_iterations=3
)

# Access results
selected_route = result['selected_route']
risk_assessment = result['risk_assessments'][-1]
print(f"Route: {selected_route['route_name']}")
print(f"Risk: {risk_assessment['risk_level']}")
```

## Configuration

Edit `.env` file to customize:

```bash
# Groq API
GROQ_API_KEY=your_key_here

# Models (choose from Groq's available models)
NAVIGATOR_MODEL=mixtral-8x7b-32768
BIOLOGIST_MODEL=mixtral-8x7b-32768
RISK_MANAGER_MODEL=llama3-70b-8192

# Routing Parameters
DEFAULT_SHIP_SPEED_KNOTS=18
REDUCED_SPEED_KNOTS=10
RISK_THRESHOLD_HIGH=50
RISK_THRESHOLD_MEDIUM=10
```

## Project Structure

```
cetacean-router/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env                      # Configuration (create from .env.example)
├── main.py                   # Main CLI entry point
│
├── config/
│   └── settings.py          # Centralized configuration
│
├── agents/                   # AI Agent implementations
│   ├── navigator.py         # Route calculation agent
│   ├── biologist.py         # Ecological assessment agent
│   └── risk_manager.py      # Decision-making agent
│
├── graph/
│   └── routing_graph.py     # LangGraph workflow definition
│
├── mcp_servers/             # Model Context Protocol servers
│   ├── obis_server.py       # Marine biology data (OBIS)
│   └── route_calc_server.py # Route calculations
│
├── api/                      # FastAPI REST API
│   ├── main.py              # API endpoints
│   └── models.py            # Pydantic models
│
└── utils/
    └── geometry.py          # Geospatial utilities
```

## How It Works

### The Optimization Loop

1. **Navigator** proposes initial direct route
2. **Biologist** queries OBIS database for cetacean sightings along route
3. If **HIGH RISK** detected:
   - **Navigator** calculates alternatives (detour or reduced speed)
   - **Biologist** re-assesses new routes
4. **Risk Manager** evaluates all options using composite scoring:
   - ETA efficiency (40 points)
   - Distance efficiency (30 points)
   - Ecological safety (30 points)
5. **Risk Manager** uses Groq LLM for strategic analysis
6. System iterates until acceptable route found or max iterations reached

### Scoring Algorithm

```python
composite_score = (
    eta_score +      # Lower ETA = better (max 40 pts)
    distance_score + # Shorter route = better (max 30 pts)
    risk_score       # Lower ecological risk = better (max 30 pts)
)
```

### Risk Levels

- **LOW** (0-10 sightings): Proceed normally
- **MEDIUM** (11-50 sightings): Consider speed reduction
- **HIGH** (50+ sightings): Require detour or significant speed reduction

## Data Sources

### OBIS (Ocean Biodiversity Information System)
- **Free, open-access** global marine species database
- 100M+ occurrence records
- Accessed via `pyobis` Python library
- Real scientific observation data

### Route Calculations
- Haversine formula for great circle distances
- Spherical geometry for accurate maritime navigation
- Custom algorithms for waypoint generation

## Example Output

```
==================================================================
CETACEAN-AWARE LOGISTICS ROUTER
==================================================================
Start: (34.4208, -119.6982)
End: (45.5152, -122.6784)

[Navigator Agent] Calculating route options...
Navigator reasoning: The direct route offers optimal efficiency...

[Biologist Agent] Assessing ecological risk...
  Route Alpha (Direct): HIGH (67 sightings)

[Navigator Agent] Calculating route options...
  Route Beta (Detour): 540nm, +2.5hrs
  Route Gamma (Reduced Speed): 500nm, +8hrs

[Risk Manager Agent] Evaluating options...

Selected: Route Beta (Detour)
Score: 82.5/100
Approved: True

==================================================================
FINAL ROUTING DECISION
==================================================================

✓ Selected Route: Route Beta (Detour)
  Distance: 540.0 nautical miles
  ETA: 30.0 hours (1.2 days)
  Speed: 18.0 knots
  Waypoints: 3

🐋 Ecological Assessment:
  Risk Level: MEDIUM
  Cetacean Sightings: 23
  Species Detected: 2

📊 Decision Metrics:
  Approved: ✓ Yes
  Iterations: 2
  Routes Evaluated: 3

💡 Rationale:
  Selected Route Beta (Detour) with composite score 82.5/100...

🤖 AI Analysis:
  Recommend Route Beta (Detour). While adding 2.5 hours...
```

## MCP Server Details

### OBIS Server (`mcp_servers/obis_server.py`)

**Tools:**
- `check_species_risk(wkt_geometry, taxon)` - Query marine mammal sightings
- `get_sector_details(lat_min, lat_max, lon_min, lon_max)` - Detailed sector analysis

**Protocol:** FastMCP  
**Data Source:** OBIS API via pyobis

### Route Calculator Server (`mcp_servers/route_calc_server.py`)

**Tools:**
- `calculate_route_metrics(waypoints, speed_knots)` - Comprehensive route metrics
- `generate_detour_waypoints(start, end, avoid_sector)` - Alternative route generation

**Protocol:** FastMCP  
**Calculations:** Haversine distance, ETA, fuel estimates

## Advanced Usage

### Custom Risk Thresholds

```python
from config.settings import settings

# Modify thresholds
settings.risk_threshold_high = 75
settings.risk_threshold_medium = 20
```

### Multi-Species Assessment

```python
# Assess specific species
result = check_species_risk(
    wkt_geometry="POLYGON(...)",
    taxon="Balaenoptera musculus"  # Blue whale only
)
```

### Custom Detour Margins

```python
from mcp_servers.route_calc_server import generate_detour_waypoints

detour = generate_detour_waypoints(
    start=[34.0, -120.0],
    end=[37.0, -122.0],
    avoid_sector={...},
    detour_margin_degrees=2.0  # Wider safety margin
)
```

## Limitations

1. **OBIS Data Coverage**: Historical observations may not reflect current migrations
2. **Weather**: Does not account for storms or sea conditions
3. **Traffic**: No integration with real-time AIS ship traffic
4. **Fuel Model**: Simplified fuel consumption calculations
5. **API Rate Limits**: OBIS queries should be rate-limited for production

## Production Deployment

For production use:

1. **Implement caching** for OBIS queries
2. **Add real-time AIS** data integration
3. **Include weather** routing
4. **Add authentication** to API
5. **Deploy MCP servers** separately with proper scaling
6. **Monitor API usage** and costs
7. **Add database** for route history
8. **Implement webhooks** for route updates

## Contributing

To extend this system:

1. **Add new agents**: Create in `agents/` directory
2. **Extend workflow**: Modify `graph/routing_graph.py`
3. **Add data sources**: Create new MCP servers
4. **Improve scoring**: Update `risk_manager.py` scoring logic

## License

This project demonstrates AI-powered conservation technology.  
Use responsibly and in accordance with maritime regulations.

## Citations

- OBIS: Ocean Biodiversity Information System - [https://obis.org](https://obis.org)
- FastMCP: [https://github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)
- LangGraph: [https://github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- Groq: [https://groq.com](https://groq.com)

## Support

For issues or questions:
1. Check API key configuration in `.env`
2. Verify all dependencies installed: `pip install -r requirements.txt`
3. Test OBIS connectivity: `python -c "from pyobis import occurrences; print('OK')"`
4. Check Groq API status: [https://status.groq.com](https://status.groq.com)

---

**🐋 Protecting marine life, one route at a time.**