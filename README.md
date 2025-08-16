# Geoapify MCP Server

A comprehensive Model Context Protocol (MCP) server that provides access to Geoapify's complete suite of location-based APIs. This server enables seamless integration of geocoding, routing, places search, and geospatial services into your MCP-compatible applications.

## 🌟 Features

This server provides **14 powerful tools** covering all major location services:

### 📍 **Geocoding & Address Services**
- **`forward_geocoding`** - Convert addresses to coordinates with simplified structure
- **`reverse_geocoding`** - Convert coordinates to detailed GeoJSON address information  
- **`suggest_places`** - Real-time address suggestions and completion as GeoJSON

### 🏢 **Places & Points of Interest**
- **`places_search`** - Search POIs by categories with GeoJSON output and pagination
- **`place_details`** - Get detailed place information with original geometry

### 🗺️ **Administrative Boundaries**
- **`boundaries_part_of`** - Find parent administrative boundaries as GeoJSON
- **`boundaries_consists_of`** - Get child boundaries with pagination as GeoJSON

### 🚗 **Routing & Navigation**
- **`get_route`** - Calculate routes with step-by-step navigation and travel metrics
- **`get_travel_times`** - Generate distance/time matrices between origins and destinations
- **`generate_isoline`** - Create reachability polygons (isochrones/isodistance)
- **`combine_geometries`** - Perform geometric operations (union/intersection)

### 📮 **Postal Services**
- **`postcode_search`** - Search postcodes with Point/Polygon geometry options
- **`postcode_list`** - List postcodes with spatial filters and pagination

### 🌐 **Additional Services**
- **`ip_to_location`** - Resolve IP addresses to comprehensive location metadata

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- A [Geoapify API key](https://www.geoapify.com/) (free tier available)

### Installation

1. **Clone and setup:**
```bash
git clone <repository-url>
cd geoapify-mcp-server
uv sync
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and add your Geoapify API key:
# GEOAPIFY_KEY=your_actual_api_key_here
```

3. **Test the installation:**
```bash
uv run python test_server.py
```

### Get Your API Key

1. Visit [Geoapify.com](https://www.geoapify.com/)
2. Sign up for a free account (no credit card required)
3. Generate an API key from your dashboard
4. Free tier includes 3,000 requests/day

## 🔧 Configuration

### MCP Client Setup

#### Claude Desktop

Add this to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "geoapify": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/yourusername/geoapify-mcp-server.git",
        "geoapify-server"
      ],
      "env": {
        "GEOAPIFY_KEY": "your_api_key_here"
      }
    }
  }
}
```

#### Local Development

```json
{
  "mcpServers": {
    "geoapify": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/geoapify-mcp-server",
        "run",
        "geoapify-server"
      ],
      "env": {
        "GEOAPIFY_KEY": "your_api_key_here"
      }
    }
  }
}
```

## 📖 Usage Examples

### Geocoding Examples

**Convert address to coordinates:**
```python
{
  "tool": "forward_geocoding",
  "arguments": {
    "text": "Eiffel Tower, Paris",
    "language": "en"
  }
}
```

**Convert coordinates to address (returns GeoJSON):**
```python
{
  "tool": "reverse_geocoding",
  "arguments": {
    "lat": 48.8584,
    "lon": 2.2945,
    "language": "en"
  }
}
```

**Get address suggestions (returns GeoJSON):**
```python
{
  "tool": "suggest_places",
  "arguments": {
    "text": "Times Sq",
    "language": "en"
  }
}
```

### Places & POI Examples

**Search for restaurants (returns GeoJSON):**
```python
{
  "tool": "places_search",
  "arguments": {
    "categories": "catering.restaurant",
    "filter": "circle:-73.986923,40.758896,500",
    "language": "en",
    "page": 1
  }
}
```

**Get place details (returns single GeoJSON feature):**
```python
{
  "tool": "place_details",
  "arguments": {
    "lat": 48.8584,
    "lon": 2.2945,
    "language": "en"
  }
}
```

### Routing Examples

**Calculate route with step-by-step navigation:**
```python
{
  "tool": "get_route",
  "arguments": {
    "waypoints": ["48.8584,2.2945", "48.8566,2.3522"],
    "mode": "driving"
  }
}
```

**Generate isochrone (reachability polygon):**
```python
{
  "tool": "generate_isoline",
  "arguments": {
    "lat": 48.8584,
    "lon": 2.2945,
    "type": "time",
    "mode": "walk",
    "range": 600
  }
}
```

**Travel time matrix:**
```python
{
  "tool": "get_travel_times",
  "arguments": {
    "origins": ["48.8584,2.2945", "48.8566,2.3522"],
    "destinations": ["48.8606,2.3376", "48.8629,2.3499"],
    "mode": "driving"
  }
}
```

**Combine geometries:**
```python
{
  "tool": "combine_geometries",
  "arguments": {
    "operation": "union",
    "id": ["shape_id_1", "shape_id_2"]
  }
}
```

## 🛠️ API Reference

### Core Parameters

Most tools support these common parameters:

- **`language`** - Language code (ISO 639-1, e.g., 'en', 'fr', 'de')
- **`page`** - Page number for pagination (default: 1, 20 results per page)
- **`filter`** - Spatial filters using Geoapify DSL
- **`bias`** - Geographic bias for results
- **`mode`** - Travel mode: 'driving', 'walking', 'cycling', 'transit'

### Spatial Filters

Geoapify supports powerful spatial filtering:

```python
# Rectangular area
"filter": "rect:west,south,east,north"

# Circular area  
"filter": "circle:lon,lat,radius_meters"

# Country restriction
"filter": "countrycode:us,ca"

# Combined filters
"filter": "rect:-74.1,40.7,-73.9,40.8|countrycode:us"
```

### Error Handling

The server provides comprehensive error handling:

- **Validation errors** for invalid coordinates or missing parameters
- **API errors** with detailed messages from Geoapify
- **Network errors** with retry suggestions
- **Rate limit handling** with clear error messages

## 🧪 Development

### Running Tests

```bash
# Run all tests
uv run python test_server.py

# Test specific functionality
uv run python -c "
from geoapify_mcp_server.server import load_tool_schemas, TOOL_FUNCTIONS
print(f'Loaded {len(load_tool_schemas())} tools')
print(f'Mapped {len(TOOL_FUNCTIONS)} functions')
"
```

### Project Structure

```
geoapify-mcp-server/
├── geoapify_mcp_server/
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # Entry point
│   ├── server.py            # MCP server implementation
│   ├── handlers.py          # Tool implementations
│   └── tools.json           # Tool schemas
├── test_server.py           # Test suite
├── test_cases.json          # Test definitions
├── main.py                  # Compatibility wrapper
├── pyproject.toml           # Project configuration
├── .env.example             # Environment template
└── README.md                # This file
```

### Adding New Tools

1. Add tool schema to `geoapify_mcp_server/tools.json`
2. Implement handler function in `geoapify_mcp_server/handlers.py`
3. Add function to `TOOL_FUNCTIONS` mapping
4. Create test cases in `test_cases.json`
5. Run tests to verify

## 📊 Supported APIs

This server implements **14 core Geoapify APIs**:

| API Category | Tools | Description |
|--------------|-------|-------------|
| Geocoding | 3 | Address ↔ Coordinates conversion with GeoJSON |
| Places | 2 | POI search and details with GeoJSON |
| Boundaries | 2 | Administrative boundary data with GeoJSON |
| Routing | 4 | Routes, travel times, isolines, geometry ops |
| Postcode | 2 | Postal code services with GeoJSON |
| Utilities | 1 | IP location with comprehensive metadata |

## 🎯 Use Cases

Perfect for applications requiring:

- **Address validation and standardization**
- **Location-based search and discovery**  
- **Route planning and optimization**
- **Delivery and logistics management**
- **Geographic data analysis**
- **Real estate and mapping applications**
- **Travel and navigation services**
- **Location intelligence and insights**

## 🔒 Security & Privacy

- API keys stored securely in environment variables
- No data persistence or logging of sensitive information
- All requests made directly to Geoapify's secure APIs
- Follows MCP security best practices

## 📝 License

This project is licensed under the MIT License. See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

- **Geoapify API Issues**: [Geoapify Documentation](https://apidocs.geoapify.com/)
- **MCP Server Issues**: Open an issue on GitHub
- **Feature Requests**: Open an issue with enhancement label

## 🙏 Acknowledgments

- [Geoapify](https://www.geoapify.com/) for providing excellent location APIs
- [Model Context Protocol](https://github.com/modelcontextprotocol) for the MCP specification
- The open-source community for continuous inspiration