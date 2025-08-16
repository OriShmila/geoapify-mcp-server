"""
Geoapify MCP Server Handlers

This module implements all the tool functions for the Geoapify MCP server.
Each function corresponds to a tool defined in tools.json and implements
the actual API calls to Geoapify services.
"""

import os
import asyncio
import httpx
from typing import Dict, Any, Optional, Union, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_KEY")
# Base URL for Geoapify API
GEOAPIFY_BASE_URL = "https://api.geoapify.com"


async def geoapify_request(
    endpoint: str,
    params: Dict[str, Any],
    method: str = "GET",
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generic function to make requests to Geoapify API.

    Args:
        endpoint: API endpoint (e.g., "/v1/geocode/search")
        params: Query parameters
        method: HTTP method (GET or POST)
        json_body: JSON body for POST requests

    Returns:
        API response as dictionary

    Raises:
        ValueError: If API key is not set or API returns an error
    """
    if not GEOAPIFY_API_KEY:
        raise ValueError("GEOAPIFY_KEY environment variable not set")

    # Add API key to parameters
    params = params.copy()
    params["apiKey"] = GEOAPIFY_API_KEY

    url = f"{GEOAPIFY_BASE_URL}{endpoint}"

    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == "POST":
                response = await client.post(url, params=params, json=json_body)
            else:
                response = await client.get(url, params=params)

            # Check for HTTP errors
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", response.text)
                except Exception:
                    error_msg = response.text
                raise ValueError(
                    f"Geoapify API error ({response.status_code}): {error_msg}"
                )

            return response.json()

        except httpx.RequestError as e:
            raise ValueError(f"Request error: {e}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Unexpected error: {e}")


# ============================================================================
# GEOCODING TOOLS
# ============================================================================


async def forward_geocoding(
    text: str,
    language: Optional[str] = None,
    filter: Optional[str] = None,
    bias: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert a free-text address or place name into geographic coordinates.

    Args:
        text: Full address or place in free text, e.g. '1600 Amphitheatre Pkwy, Mountain View, CA' or 'Eiffel Tower Paris'
        language: Preferred response language code, e.g. 'en', 'de', 'fr'
        filter: Optional filter DSL, e.g. 'rect:minLon,minLat,maxLon,maxLat' or 'countrycode:US'
        bias: Optional bias DSL, e.g. 'point:lon,lat' or 'countrycode:US'

    Returns:
        Simplified geocoding results with basic address components and coordinates
    """
    # Validate required parameter
    if not text:
        raise ValueError("text parameter is required")

    # Build parameters with hard limit of 20
    params = {"text": text, "limit": 20, "format": "json"}

    # Add optional parameters
    if language is not None:
        params["lang"] = language
    if filter is not None:
        params["filter"] = filter
    if bias is not None:
        params["bias"] = bias

    # Make the API request
    response = await geoapify_request("/v1/geocode/search", params)

    # Transform the response to match the simplified schema
    if "features" in response:
        # Handle GeoJSON format response
        results = []
        for feature in response["features"]:
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [])

            result = {
                "formatted": props.get("formatted", ""),
                "lat": coordinates[1] if len(coordinates) >= 2 else None,
                "lon": coordinates[0] if len(coordinates) >= 2 else None,
            }

            # Add optional fields if they exist
            for field in [
                "country",
                "state",
                "county",
                "city",
                "postcode",
                "street",
                "housenumber",
            ]:
                if field in props:
                    result[field] = props[field]

            results.append(result)

        return {"results": results}

    elif "results" in response:
        # Handle JSON format response - already in the right format
        simplified_results = []
        for result in response["results"]:
            simplified_result = {
                "formatted": result.get("formatted", ""),
                "lat": result.get("lat"),
                "lon": result.get("lon"),
            }

            # Add optional fields if they exist
            for field in [
                "country",
                "state",
                "county",
                "city",
                "postcode",
                "street",
                "housenumber",
            ]:
                if field in result:
                    simplified_result[field] = result[field]

            simplified_results.append(simplified_result)

        return {"results": simplified_results}

    else:
        # Fallback - return empty results
        return {"results": []}


async def reverse_geocoding(
    lat: float,
    lon: float,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert coordinates to the nearest address/place. Returns up to 20 results as GeoJSON.

    Args:
        lat: Latitude coordinate (-90 to 90)
        lon: Longitude coordinate (-180 to 180)
        language: Preferred response language code, e.g. 'en', 'de', 'fr'

    Returns:
        GeoJSON FeatureCollection with reverse geocoding results
    """
    # Validate coordinates
    if not (-90 <= lat <= 90):
        raise ValueError("Latitude must be between -90 and 90")
    if not (-180 <= lon <= 180):
        raise ValueError("Longitude must be between -180 and 180")

    # Build parameters with hard limit of 20 and force GeoJSON format
    params = {"lat": lat, "lon": lon, "limit": 20, "format": "geojson"}

    # Add optional language parameter
    if language is not None:
        params["lang"] = language

    return await geoapify_request("/v1/geocode/reverse", params)


async def suggest_places(
    text: str,
    language: Optional[str] = None,
    filter: Optional[str] = None,
    bias: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Suggest addresses and places for partial text input. Returns up to 20 GeoJSON Point features.

    Args:
        text: Partial input (e.g., '1600 Amph...', 'Eiffel To...')
        language: Preferred response language code, e.g. 'en', 'de', 'fr'
        filter: Optional filter DSL, e.g. 'rect:minLon,minLat,maxLon,maxLat' or 'countrycode:US'
        bias: Optional bias DSL, e.g. 'point:lon,lat' or 'countrycode:US'

    Returns:
        GeoJSON FeatureCollection with place suggestions
    """
    # Validate input
    if not text:
        raise ValueError("text parameter is required")

    # Build parameters with hard limit of 20 and force GeoJSON format
    params = {"text": text, "limit": 20, "format": "geojson"}

    # Add optional parameters
    if language is not None:
        params["lang"] = language
    if filter is not None:
        params["filter"] = filter
    if bias is not None:
        params["bias"] = bias

    return await geoapify_request("/v1/geocode/autocomplete", params)


# ============================================================================
# PLACES AND POI TOOLS
# ============================================================================


async def places_search(
    categories: str,
    filter: Optional[str] = None,
    bias: Optional[str] = None,
    page: Optional[int] = 1,
    language: Optional[str] = None,
    conditions: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search for places (POIs) by categories with spatial filters, bias, language, and pagination.

    Args:
        categories: Comma-separated category codes (e.g. accommodation.hotel, activity.sport_club)
        filter: Spatial filter, e.g. rect:minx,miny,maxx,maxy | circle:lon,lat,radius | place:city | countrycode:US
        bias: Bias results toward location, e.g. point:lon,lat | rect:minx,miny,maxx,maxy | countrycode:US
        page: Page number for results (20 per page)
        language: Language code (e.g. en, de, fr)
        conditions: Optional conditions (e.g. opening_hours:24/7)

    Returns:
        GeoJSON FeatureCollection with places search results
    """
    if not categories:
        raise ValueError("categories parameter is required")

    # Calculate offset from page number (20 results per page)
    if page is None:
        page = 1
    offset = (page - 1) * 20

    # Build parameters with hard limit of 20 and force GeoJSON format
    params = {
        "categories": categories,
        "limit": 20,
        "offset": offset,
        "format": "geojson",
    }

    # Add optional parameters
    if filter is not None:
        params["filter"] = filter
    if bias is not None:
        params["bias"] = bias
    if language is not None:
        params["lang"] = language
    if conditions is not None:
        params["conditions"] = conditions

    return await geoapify_request("/v2/places", params)


async def place_details(
    id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get details for a place by id or coordinates. Returns a single GeoJSON Feature with the ORIGINAL geometry.

    Args:
        id: Place id from places_search/forward_geocoding
        lat: Latitude
        lon: Longitude
        language: Language code, e.g. 'en', 'de', 'fr'

    Returns:
        Single GeoJSON Feature with original geometry (Point, Polygon, or MultiPolygon)
    """
    if not id and not (lat is not None and lon is not None):
        raise ValueError("Either 'id' or both 'lat' and 'lon' parameters are required")

    # Build parameters
    params = {"features": "details"}

    # Add location parameters
    if id is not None:
        params["id"] = id
    if lat is not None:
        params["lat"] = lat
    if lon is not None:
        params["lon"] = lon

    # Add language parameter
    if language is not None:
        params["lang"] = language

    # Make the API request
    response = await geoapify_request("/v2/place-details", params)

    # Return the first feature with original geometry
    if "features" in response and len(response["features"]) > 0:
        return response["features"][0]
    else:
        # If no features found, return empty Feature with Point geometry
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    lon if lon is not None else 0,
                    lat if lat is not None else 0,
                ],
            },
            "properties": {
                "formatted": "No details found",
            },
        }


# ============================================================================
# BOUNDARIES TOOLS
# ============================================================================


async def boundaries_part_of(
    id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    boundaries: Optional[str] = None,
    sublevel: Optional[int] = None,
    geometry_level: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return parent boundaries (admin/other) for a place or boundary. Always a GeoJSON FeatureCollection of area polygons.

    Args:
        id: Boundary or place id
        lat: Latitude
        lon: Longitude
        boundaries: Boundary class to query
        sublevel: If set, return parents only up to this administrative level (e.g., 2=country, 4=state/region)
        geometry_level: Geometry simplification level for returned boundaries
        language: Response language code, e.g. 'en', 'de', 'fr'

    Returns:
        Parent boundaries as GeoJSON FeatureCollection
    """
    if not id and not (lat is not None and lon is not None):
        raise ValueError("Either 'id' or both 'lat' and 'lon' parameters are required")

    params = {"format": "geojson"}

    # Add location parameters
    if id is not None:
        params["id"] = id
    if lat is not None:
        params["lat"] = lat
    if lon is not None:
        params["lon"] = lon

    # Add optional parameters
    if boundaries is not None:
        params["boundaries"] = boundaries
    if sublevel is not None:
        params["sublevel"] = sublevel
    if geometry_level is not None:
        params["geometry"] = geometry_level  # API still uses 'geometry' parameter
    if language is not None:
        params["lang"] = language  # API still uses 'lang' parameter

    return await geoapify_request("/v1/boundaries/part-of", params)


async def boundaries_consists_of(
    id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    boundaries: Optional[str] = None,
    sublevel: Optional[int] = None,
    geometry_level: Optional[str] = None,
    page: Optional[int] = 1,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return child boundaries (subdivisions) for a boundary or place. Always a GeoJSON FeatureCollection of area polygons.

    Args:
        id: Parent boundary or place id
        lat: Latitude
        lon: Longitude
        boundaries: Boundary class for children
        sublevel: If set, return children at this exact administrative level
        geometry_level: Geometry simplification level for returned boundaries
        page: Page number (20 results per page)
        language: Response language code, e.g. 'en', 'de', 'fr'

    Returns:
        Child boundaries as GeoJSON FeatureCollection
    """
    if not id and not (lat is not None and lon is not None):
        raise ValueError("Either 'id' or both 'lat' and 'lon' parameters are required")

    # Calculate offset from page number (20 results per page)
    if page is None:
        page = 1
    offset = (page - 1) * 20

    params = {"format": "geojson", "limit": 20, "offset": offset}

    # Add location parameters
    if id is not None:
        params["id"] = id
    if lat is not None:
        params["lat"] = lat
    if lon is not None:
        params["lon"] = lon

    # Add optional parameters
    if boundaries is not None:
        params["boundaries"] = boundaries
    if sublevel is not None:
        params["sublevel"] = sublevel
    if geometry_level is not None:
        params["geometry"] = geometry_level  # API still uses 'geometry' parameter
    if language is not None:
        params["lang"] = language  # API still uses 'lang' parameter

    return await geoapify_request("/v1/boundaries/consists-of", params)


# ============================================================================
# ROUTING AND NAVIGATION TOOLS
# ============================================================================


async def generate_isoline(
    lat: float,
    lon: float,
    type: str,
    mode: str,
    range: Union[int, str, List[int]],
    avoid: Optional[str] = None,
    traffic: Optional[str] = None,
    route_type: Optional[str] = None,
    units: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute reachability polygons by time or distance for a travel mode.

    Args:
        lat: Latitude
        lon: Longitude
        type: Measure type (time or distance)
        mode: Travel mode (drive, truck, bicycle, walk, transit)
        range: Seconds (time) or meters (distance). Array => multiple contours
        avoid: DSL: tolls|highways|ferries|...
        traffic: Traffic consideration
        route_type: Route optimization type
        units: Units system

    Returns:
        GeoJSON FeatureCollection with isoline polygons
    """
    if not all([lat is not None, lon is not None, type, mode, range is not None]):
        raise ValueError("lat, lon, type, mode, and range parameters are required")

    params = {"lat": lat, "lon": lon, "type": type, "mode": mode}

    # Handle range parameter (can be int, string, or list)
    if isinstance(range, list):
        params["range"] = ",".join(map(str, range))
    else:
        params["range"] = str(range)

    # Add optional parameters
    for param_name, param_value in locals().items():
        if (
            param_name not in ["params", "lat", "lon", "type", "mode", "range"]
            and param_value is not None
        ):
            params[param_name] = param_value

    result = await geoapify_request("/v1/isoline", params)

    # Check if we got an async job response instead of direct result
    if isinstance(result, dict) and "id" in result and "features" not in result:
        # This is an async job, we need to fetch the result
        job_id = result["id"]
        # Wait a moment for the job to complete
        await asyncio.sleep(0.2)
        # Fetch the job result
        job_result = await geoapify_request("/v1/batch", {"id": job_id})
        return job_result

    return result


async def combine_geometries(
    operation: str,
    id: List[str],
) -> Dict[str, Any]:
    """
    Combine previously generated shapes using union or intersection.

    Args:
        operation: Geometric operation (union or intersection)
        id: IDs of shapes to combine

    Returns:
        GeoJSON FeatureCollection with combined geometry
    """
    if not operation:
        raise ValueError("operation parameter is required")
    if not id or len(id) < 2:
        raise ValueError("id parameter must be an array with at least 2 elements")

    params = {"operation": operation, "id": ",".join(id)}

    return await geoapify_request("/v1/geometry", params)


async def get_route(
    waypoints: List[str],
    mode: Optional[str] = "driving",
) -> Dict[str, Any]:
    """
    Calculate a route with step-by-step navigation, total distance, and travel time.

    Args:
        waypoints: List of locations or coordinates in order (start → via → destination)
        mode: Travel mode for the route (driving, walking, cycling, transit)

    Returns:
        Route with distance_km, duration_min, steps, and geometry
    """
    if not waypoints or len(waypoints) < 2:
        raise ValueError("At least 2 waypoints are required")

    # Map mode names from new schema to Geoapify API
    mode_mapping = {
        "driving": "drive",
        "walking": "walk",
        "cycling": "bicycle",
        "transit": "transit",
    }
    api_mode = mode_mapping.get(mode, "drive")

    # Convert waypoints list to pipe-separated string of lat,lon pairs
    # For now, assume waypoints are already in "lat,lon" format
    waypoints_str = "|".join(waypoints)

    params = {
        "waypoints": waypoints_str,
        "mode": api_mode,
        "details": "instruction_text",
        "format": "geojson",
    }

    result = await geoapify_request("/v1/routing", params)

    # Transform the response to match our simplified schema
    if result.get("features") and len(result["features"]) > 0:
        route_feature = result["features"][0]
        properties = route_feature.get("properties", {})

        # Extract total distance and time
        distance_m = properties.get("distance", 0)
        distance_km = distance_m / 1000

        time_s = properties.get("time", 0)
        duration_min = time_s / 60

        # Extract steps from legs
        steps = []
        legs = properties.get("legs", [])
        for leg in legs:
            leg_steps = leg.get("steps", [])
            for step in leg_steps:
                instruction = step.get("instruction", {})
                steps.append(
                    {
                        "instruction": instruction.get("text", ""),
                        "distance_m": step.get("distance", 0),
                        "duration_s": step.get("time", 0),
                    }
                )

        # Extract geometry
        geometry = route_feature.get("geometry", {})

        return {
            "distance_km": round(distance_km, 2),
            "duration_min": round(duration_min, 1),
            "steps": steps,
            "geometry": geometry,
        }

    # Fallback if no route found
    return {
        "distance_km": 0,
        "duration_min": 0,
        "steps": [],
        "geometry": {"type": "LineString", "coordinates": []},
    }


async def get_travel_times(
    origins: List[str],
    destinations: List[str],
    mode: Optional[str] = "driving",
) -> Dict[str, Any]:
    """
    Compare travel distances and durations between multiple origins and destinations in a matrix format.

    Args:
        origins: List of starting locations or coordinates
        destinations: List of target locations or coordinates
        mode: Travel mode for the calculations (driving, walking, cycling, transit)

    Returns:
        Matrix of distances and times
    """
    if not origins or len(origins) == 0:
        raise ValueError("At least one origin is required")
    if not destinations or len(destinations) == 0:
        raise ValueError("At least one destination is required")

    # Map mode names from new schema to Geoapify API
    mode_mapping = {
        "driving": "drive",
        "walking": "walk",
        "cycling": "bicycle",
        "transit": "transit",
    }
    api_mode = mode_mapping.get(mode, "drive")

    # Convert string locations to source/target format
    sources = []
    for origin in origins:
        # Parse coordinates from "lat,lon" format
        if "," in origin:
            parts = origin.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    sources.append({"location": [lon, lat]})
                except ValueError:
                    # If parsing fails, skip this origin
                    pass

    targets = []
    for dest in destinations:
        # Parse coordinates from "lat,lon" format
        if "," in dest:
            parts = dest.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    targets.append({"location": [lon, lat]})
                except ValueError:
                    # If parsing fails, skip this destination
                    pass

    if not sources:
        raise ValueError("No valid origins provided")
    if not targets:
        raise ValueError("No valid destinations provided")

    # Build request body
    body = {"mode": api_mode, "sources": sources, "targets": targets}

    result = await geoapify_request(
        "/v1/routematrix", {}, method="POST", json_body=body
    )

    # Transform the response to match our simplified schema
    # The API returns a flat array, we need to convert to 2D matrix
    matrix = []
    # Handle both dict and list responses
    if isinstance(result, dict):
        sources_to_targets = result.get("sources_to_targets", [])
    elif isinstance(result, list):
        sources_to_targets = result
    else:
        sources_to_targets = []

    num_sources = len(sources)
    num_targets = len(targets)

    # Check if sources_to_targets is already a 2D matrix or a flat list
    if sources_to_targets and isinstance(sources_to_targets[0], list):
        # Already a 2D matrix
        for row_data in sources_to_targets:
            row = []
            for entry in row_data:
                if entry and isinstance(entry, dict):
                    distance_m = entry.get("distance", 0)
                    time_s = entry.get("time", 0)
                    row.append(
                        {
                            "distance_km": round(distance_m / 1000, 2),
                            "duration_min": round(time_s / 60, 1),
                        }
                    )
                else:
                    row.append({"distance_km": None, "duration_min": None})
            matrix.append(row)
    else:
        # Flat list - convert to 2D matrix
        for i in range(num_sources):
            row = []
            for j in range(num_targets):
                # Find the entry for this source-target pair
                idx = i * num_targets + j
                if idx < len(sources_to_targets):
                    entry = sources_to_targets[idx]
                    if entry and isinstance(entry, dict):
                        distance_m = entry.get("distance", 0)
                        time_s = entry.get("time", 0)
                        row.append(
                            {
                                "distance_km": round(distance_m / 1000, 2),
                                "duration_min": round(time_s / 60, 1),
                            }
                        )
                    else:
                        # No route found
                        row.append({"distance_km": None, "duration_min": None})
                else:
                    row.append({"distance_km": None, "duration_min": None})
            matrix.append(row)

    return {"matrix": matrix}


async def map_matching(
    mode: str,
    waypoints: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Snap raw GPS tracks to the road network.

    Args:
        mode: Travel mode
        waypoints: Array of GPS track points

    Returns:
        Matched route geometry as GeoJSON
    """
    if not mode:
        raise ValueError("mode parameter is required")
    if not waypoints:
        raise ValueError("waypoints parameter is required")

    # Build request body
    body = {"mode": mode, "waypoints": waypoints}

    return await geoapify_request("/v1/mapmatching", {}, method="POST", json_body=body)


async def route_planner(
    mode: str,
    agents: Optional[List[Dict[str, Any]]] = None,
    jobs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Optimize routes for multiple agents (Vehicle Routing Problem).

    Args:
        mode: Travel mode
        agents: Array of agents
        jobs: Array of jobs

    Returns:
        Optimized routes as GeoJSON
    """
    if not mode:
        raise ValueError("mode parameter is required")

    # Build request body
    body = {"mode": mode}

    if agents is not None:
        body["agents"] = agents
    if jobs is not None:
        body["jobs"] = jobs

    return await geoapify_request("/v1/routeplanner", {}, method="POST", json_body=body)


# ============================================================================
# POSTCODE TOOLS
# ============================================================================


async def postcode_search(
    postcode: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    country_code: Optional[str] = None,
    geometry_mode: Optional[str] = "point",
    language: Optional[str] = None,
    page: Optional[int] = 1,
) -> Dict[str, Any]:
    """
    Find a postcode by text or by location. Returns up to 20 results as a GeoJSON FeatureCollection.

    Args:
        postcode: Postcode to search for
        lat: Latitude
        lon: Longitude
        country_code: ISO 3166-1 alpha-2, lowercase
        geometry_mode: Return centroid points or original postcode polygons when available
        language: Language code, e.g. 'en', 'de', 'fr'
        page: 1-based page index; each page returns up to 20 results

    Returns:
        GeoJSON FeatureCollection with postcode results
    """
    if not postcode and not (lat is not None and lon is not None):
        raise ValueError(
            "Either 'postcode' or both 'lat' and 'lon' parameters are required"
        )

    # Calculate pagination offset
    offset = (page - 1) * 20

    params = {
        "format": "geojson",
        "limit": 20,
        "offset": offset,
    }

    # Add location parameters
    if postcode is not None:
        params["postcode"] = postcode
    if lat is not None:
        params["lat"] = lat
    if lon is not None:
        params["lon"] = lon

    # Add optional parameters with API parameter mapping
    if country_code is not None:
        params["countrycode"] = country_code
    if geometry_mode == "polygon":
        params["geometry"] = "original"
    else:
        params["geometry"] = "point"
    if language is not None:
        params["lang"] = language

    response = await geoapify_request("/v1/postcode/search", params)

    # Ensure we always return a FeatureCollection with proper properties
    if response.get("type") == "FeatureCollection":
        # Already a FeatureCollection - fix any malformed features
        for feature in response.get("features", []):
            # Fix nested geometry structure if it exists (Geoapify bug workaround)
            if feature.get("geometry") and isinstance(feature["geometry"], dict):
                geom = feature["geometry"]
                # Check if geometry is actually a nested Feature
                if geom.get("type") == "Feature" and "geometry" in geom:
                    # Extract the actual geometry from the nested structure
                    feature["geometry"] = geom["geometry"]

            if not feature.get("properties"):
                feature["properties"] = {}
            props = feature["properties"]

            # Ensure postcode and country_code are always present
            if "postcode" not in props:
                props["postcode"] = postcode or ""
            if "country_code" not in props:
                props["country_code"] = country_code or ""

    elif response.get("type") == "Feature":
        # Single feature - wrap in FeatureCollection
        feature = response

        # Fix nested geometry structure if it exists (Geoapify bug workaround)
        if feature.get("geometry") and isinstance(feature["geometry"], dict):
            geom = feature["geometry"]
            # Check if geometry is actually a nested Feature
            if geom.get("type") == "Feature" and "geometry" in geom:
                # Extract the actual geometry from the nested structure
                feature["geometry"] = geom["geometry"]

        if not feature.get("properties"):
            feature["properties"] = {}
        props = feature["properties"]

        # Ensure postcode and country_code are always present
        if "postcode" not in props:
            props["postcode"] = postcode or ""
        if "country_code" not in props:
            props["country_code"] = country_code or ""

        response = {"type": "FeatureCollection", "features": [feature]}
    else:
        # Handle other response formats (shouldn't happen with format=geojson)
        # Create a minimal valid FeatureCollection
        response = {"type": "FeatureCollection", "features": []}

    return response


async def postcode_list(
    text: Optional[str] = None,
    filter: Optional[str] = None,
    bias: Optional[str] = None,
    country_code: Optional[str] = None,
    geometry_mode: Optional[str] = "point",
    language: Optional[str] = None,
    page: Optional[int] = 1,
) -> Dict[str, Any]:
    """
    List postcodes within a spatial/text filter. Always returns a GeoJSON FeatureCollection with up to 20 results per page.

    Args:
        text: Free-text filter (postcode, place name)
        filter: Spatial filter DSL: rect:minLon,minLat,maxLon,maxLat | circle:lon,lat,radius_m | place:ID | countrycode:XX
        bias: Bias DSL: point:lon,lat | rect:... | countrycode:XX
        country_code: ISO 3166-1 alpha-2, lowercase
        geometry_mode: Return centroid points or original postcode polygons when available
        language: Language code, e.g. 'en', 'de', 'fr'
        page: 1-based page index; each page returns up to 20 results

    Returns:
        GeoJSON FeatureCollection with postcode results
    """
    # Calculate pagination offset
    offset = (page - 1) * 20

    params = {
        "format": "geojson",
        "limit": 20,
        "offset": offset,
    }

    # Add optional parameters with API parameter mapping
    if text is not None:
        params["text"] = text
    if filter is not None:
        params["filter"] = filter
    if bias is not None:
        params["bias"] = bias
    if country_code is not None:
        params["countrycode"] = country_code
    if geometry_mode == "polygon":
        params["geometry"] = "original"
    else:
        params["geometry"] = "point"
    if language is not None:
        params["lang"] = language

    return await geoapify_request("/v1/postcode/list", params)


# ============================================================================
# IP GEOLOCATION TOOLS
# ============================================================================


async def ip_to_location(
    ip: str,
) -> Dict[str, Any]:
    """
    Resolve an IP (IPv4/IPv6) to approximate location and country metadata.

    Args:
        ip: IP address (IPv4 or IPv6)

    Returns:
        IP geolocation data with comprehensive location and metadata
    """
    if not ip:
        raise ValueError("ip parameter is required")

    params = {"ip": ip}
    response = await geoapify_request("/v1/ipinfo", params)

    # Transform nested API response to flat schema structure
    result = {
        "ip": response.get("ip", ip),
        "ip_version": "IPv6" if ":" in ip else "IPv4",
    }

    # Location data
    location = response.get("location", {})
    result["latitude"] = location.get("latitude")
    result["longitude"] = location.get("longitude")
    result["accuracy_radius_m"] = location.get("accuracy_radius")

    # Continent data
    continent = response.get("continent", {})
    result["continent_code"] = continent.get("code")
    result["continent_name"] = continent.get("name")

    # Country data
    country = response.get("country", {})
    result["country_code"] = country.get("iso_code")
    result["country_name"] = country.get("name")
    result["phone_code"] = country.get("phone_code")
    result["capital"] = country.get("capital")
    result["currency_code"] = country.get("currency")
    result["flag_url"] = country.get("flag")

    # Regional data
    region = response.get("region", {})
    result["region"] = region.get("name")

    state = response.get("state", {})
    result["state"] = state.get("name")

    city = response.get("city", {})
    result["city"] = city.get("name")

    # Languages (flatten if nested)
    languages = country.get("languages", [])
    if languages:
        result["languages"] = []
        for lang in languages:
            if isinstance(lang, str):
                result["languages"].append(lang)
            elif isinstance(lang, dict):
                result["languages"].append(
                    lang.get("name", lang.get("iso_code", str(lang)))
                )

    # Network information (if available)
    result["network_cidr"] = response.get("network", {}).get("cidr")
    result["asn"] = response.get("asn", {}).get("number")
    result["organization"] = response.get("asn", {}).get("organization")

    # Timezone information (if available)
    timezone = response.get("timezone", {})
    result["time_zone"] = timezone.get("name")
    result["utc_offset_seconds"] = timezone.get("offset_seconds")

    # Security flags (if available)
    result["is_proxy"] = response.get("security", {}).get("is_proxy", False)
    result["is_vpn"] = response.get("security", {}).get("is_vpn", False)
    result["is_tor"] = response.get("security", {}).get("is_tor", False)

    # Currency details (if available)
    currency = response.get("currency", {})
    if currency:
        result["currency_name"] = currency.get("name")
        result["currency_symbol"] = currency.get("symbol")

    # Datasources
    datasource = response.get("datasource")
    if datasource:
        if isinstance(datasource, list):
            result["datasources"] = datasource
        else:
            result["datasources"] = [datasource]

    # Remove None values to clean up response
    return {k: v for k, v in result.items() if v is not None}


# ============================================================================
# TOOL FUNCTIONS MAPPING
# ============================================================================

TOOL_FUNCTIONS = {
    "forward_geocoding": forward_geocoding,
    "reverse_geocoding": reverse_geocoding,
    "suggest_places": suggest_places,
    "places_search": places_search,
    "place_details": place_details,
    "boundaries_part_of": boundaries_part_of,
    "boundaries_consists_of": boundaries_consists_of,
    "generate_isoline": generate_isoline,
    "combine_geometries": combine_geometries,
    "get_route": get_route,
    "get_travel_times": get_travel_times,
    "postcode_search": postcode_search,
    "postcode_list": postcode_list,
    "ip_to_location": ip_to_location,
}
