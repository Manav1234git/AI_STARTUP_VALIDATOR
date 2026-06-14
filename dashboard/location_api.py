"""
Location intelligence for ValidatorAI
Uses Google Maps API (with OSM fallback for free tier)
"""
import os
import requests
import json
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
import re
import time


GOOGLE_MAPS_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '').strip()


def geocode_location(query):
    """Convert location name to lat/lng. Tries Google first, then OSM."""
    
    # Try Google first
    if GOOGLE_MAPS_KEY:
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {'address': query, 'key': GOOGLE_MAPS_KEY}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            if data.get('status') == 'OK' and data.get('results'):
                loc = data['results'][0]['geometry']['location']
                formatted = data['results'][0]['formatted_address']
                return {
                    'lat': loc['lat'],
                    'lng': loc['lng'],
                    'formatted_address': formatted,
                    'source': 'google'
                }
        except Exception as e:
            print(f"[Google geocode error] {e}")
    
    # Fallback to OpenStreetMap (free, no key)
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': query,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1
        }
        headers = {'User-Agent': 'ValidatorAI/1.0'}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if data:
            return {
                'lat': float(data[0]['lat']),
                'lng': float(data[0]['lon']),
                'formatted_address': data[0].get('display_name', query),
                'source': 'openstreetmap'
            }
    except Exception as e:
        print(f"[OSM geocode error] {e}")
    
    return None


def get_nearby_places(lat, lng, keyword='business', radius=2000):
    """Find nearby businesses/places. Uses Google if available, else Overpass API."""
    
    if GOOGLE_MAPS_KEY:
        try:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f'{lat},{lng}',
                'radius': radius,
                'keyword': keyword,
                'key': GOOGLE_MAPS_KEY
            }
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            if data.get('status') == 'OK':
                return [
                    {
                        'name': p.get('name', 'Unknown'),
                        'lat': p['geometry']['location']['lat'],
                        'lng': p['geometry']['location']['lng'],
                        'rating': p.get('rating', 0),
                        'types': p.get('types', []),
                        'vicinity': p.get('vicinity', ''),
                        'source': 'google'
                    }
                    for p in data.get('results', [])[:20]
                ]
        except Exception as e:
            print(f"[Google places error] {e}")
    
    # Fallback: Overpass API (OpenStreetMap, free)
    try:
        # Overpass QL query: find businesses within radius
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:10];
        (
          node["shop"](around:{radius},{lat},{lng});
          node["amenity"~"restaurant|cafe|bank|hospital|school|pharmacy"](around:{radius},{lat},{lng});
          way["shop"](around:{radius},{lat},{lng});
        );
        out body 20;
        """
        r = requests.post(overpass_url, data={'data': query}, timeout=15)
        data = r.json()
        results = []
        for elem in data.get('elements', [])[:20]:
            tags = elem.get('tags', {})
            results.append({
                'name': tags.get('name', tags.get('amenity', tags.get('shop', 'Unknown'))),
                'lat': elem.get('lat', 0),
                'lng': elem.get('lon', 0),
                'rating': 0,  # OSM doesn't have ratings
                'types': list(tags.keys())[:3],
                'vicinity': tags.get('addr:street', ''),
                'source': 'openstreetmap'
            })
        return results
    except Exception as e:
        print(f"[Overpass API error] {e}")
        return []


def get_demand_indicators(lat, lng):
    """
    Estimate demand using multiple free data sources.
    Returns scores 0-100 for various factors.
    """
    indicators = {
        'population_density': 0,
        'business_density': 0,
        'commercial_activity': 0,
        'accessibility': 0,
        'competition_density': 0,
    }
    
    # ✅ Use Overpass API to count businesses in area (proxy for commercial activity)
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        
        # Count various amenities in 2km radius
        query = f"""
        [out:json][timeout:15];
        (
          node["amenity"~"restaurant|cafe|bank|school|hospital|pharmacy|marketplace"](around:2000,{lat},{lng});
          way["amenity"~"restaurant|cafe|bank|school|hospital|pharmacy|marketplace"](around:2000,{lat},{lng});
          node["shop"](around:2000,{lat},{lng});
          way["shop"](around:2000,{lat},{lng});
          way["highway"~"primary|secondary|tertiary"](around:1000,{lat},{lng});
        );
        out count;
        """
        r = requests.post(overpass_url, data={'data': query}, timeout=20)
        data = r.json()
        
        # Parse count from elements
        total_count = len(data.get('elements', []))
        
        # Heuristic scoring
        indicators['business_density'] = min(100, total_count * 2)
        indicators['commercial_activity'] = min(100, total_count * 1.5)
        indicators['accessibility'] = 60  # Default moderate
        indicators['population_density'] = 50  # Cannot determine without census data
        
    except Exception as e:
        print(f"[Demand indicators error] {e}")
    
    return indicators


def calculate_location_risk(lat, lng):
    """
    Calculate risk factors for a location.
    Uses heuristics based on available data.
    """
    risks = {
        'crime_risk': 35,      # Default moderate
        'flood_risk': 15,      # Default low
        'traffic_risk': 50,    # Default moderate
        'regulatory_risk': 30, # Default low-moderate
    }
    
    # ✅ Check if location is in flood-prone area (India-specific heuristics)
    # You can enhance this with actual flood data APIs
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:10];
        (
          way["waterway"~"river|stream"](around:5000,{lat},{lng});
          way["natural"="water"](around:5000,{lat},{lng});
          way["leisure"="park"](around:2000,{lat},{lng});
        );
        out count;
        """
        r = requests.post(overpass_url, data={'data': query}, timeout=15)
        data = r.json()
        water_count = len(data.get('elements', []))
        
        # Heuristic: more water bodies nearby = higher flood risk
        risks['flood_risk'] = min(80, water_count * 10)
        
        # Park/green space nearby is positive
        if water_count == 0:
            risks['crime_risk'] = max(20, risks['crime_risk'] - 10)
        
    except Exception as e:
        print(f"[Risk calculation error] {e}")
    
    return risks


@login_required
def location_intelligence(request):
    """
    API endpoint: GET /dashboard/location-intel/?location=Delhi&industry=restaurant
    Returns: geocoded location, nearby places, demand & risk indicators
    """
    location = request.GET.get('location', '').strip()
    industry = request.GET.get('industry', 'business')
    
    if not location:
        return JsonResponse({'error': 'Location parameter required'}, status=400)
    
    # Cache key
    cache_key = f"loc:{request.user.id}:{re.sub(r'\\W+', '_', location)[:30]}:{industry}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)
    
    # 1. Geocode
    geo = geocode_location(location)
    if not geo:
        return JsonResponse({'error': f'Could not find location: {location}'}, status=404)
    
    # 2. Find nearby competitors
    nearby = get_nearby_places(geo['lat'], geo['lng'], keyword=industry)
    
    # 3. Calculate demand
    demand = get_demand_indicators(geo['lat'], geo['lng'])
    
    # 4. Calculate risk
    risk = calculate_location_risk(geo['lat'], geo['lng'])
    
    # 5. Compute overall location score
    location_score = max(0, 100 - (
        risk['crime_risk'] * 0.3 +
        risk['flood_risk'] * 0.2 +
        risk['traffic_risk'] * 0.2 +
        risk['regulatory_risk'] * 0.3
    ))
    
    result = {
        'location': {
            'query': location,
            'formatted_address': geo['formatted_address'],
            'lat': geo['lat'],
            'lng': geo['lng'],
            'source': geo['source'],
        },
        'location_score': round(location_score),
        'nearby_places': nearby,
        'nearby_count': len(nearby),
        'demand_indicators': demand,
        'risk_factors': risk,
        'map_config': {
            'center': {'lat': geo['lat'], 'lng': geo['lng']},
            'zoom': 14,
            'has_google_key': bool(GOOGLE_MAPS_KEY),
        }
    }
    
    # Cache for 1 hour
    cache.set(cache_key, result, timeout=3600)
    
    return JsonResponse(result)
