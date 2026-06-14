from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from google import genai
from django.core.cache import cache
import os, json, io, re, tempfile
import requests
from urllib.parse import quote
import matplotlib
matplotlib.use('Agg')  # non-GUI backend for server
import matplotlib.pyplot as plt
from django.http import JsonResponse, HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import textwrap

# ============================================================
# GEMINI CLIENT (graceful failure — no server crash)
# ============================================================
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not API_KEY:
    print("⚠️  WARNING: GEMINI_API_KEY not set in .env — AI features will fail")
    client = None
else:
    print(f"✅ Gemini API key loaded ({API_KEY[:4]}...)")
    client = genai.Client(api_key=API_KEY)

# ============================================================
# SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT = """You are ValidatorAI, an expert startup analyst with deep knowledge of Indian and global startup ecosystems, venture capital, market research, and entrepreneurship. You analyze startup ideas with real-world data and return ONLY a valid JSON object — no markdown, no explanation, no preamble.

Analyze the given startup idea and return a comprehensive JSON with this EXACT structure:
{
  "score": <integer 0-100 overall viability>,
  "verdict_label": <"Strong Opportunity" | "Moderate Potential" | "High Risk">,
  "verdict_title": <catchy 5-8 word title for this report>,
  "summary": <2-3 sentence executive summary>,
  "market_size": <e.g. "₹4,200 Cr TAM">,
  "growth_rate": <e.g. "+28% CAGR">,
  "mrr_yr1": <e.g. "₹3L–8L/mo">,
  "breakeven": <e.g. "14–18 months">,
  "risks_breakdown": [
    {"label": "Execution Risk", "value": <0-100>, "color": <"green"|"yellow"|"red">},
    {"label": "Technical Risk", "value": <0-100>, "color": <"green"|"yellow"|"red">},
    {"label": "Market Adoption Risk", "value": <0-100>, "color": <"green"|"yellow"|"red">},
    {"label": "Regulatory Risk", "value": <0-100>, "color": <"green"|"yellow"|"red">},
    {"label": "Funding Risk", "value": <0-100>, "color": <"green"|"yellow"|"red">}
  ],
  "risk_warning": <most critical risk in 1-2 sentences or null>,
  "risk_warning_title": <short title>,
  "market_fit": {
    "score": <integer 1-10>,
    "label": <e.g. "Strong PMF Indicators">,
    "description": <2 sentences>,
    "icp": [
      {"icon": "🏪", "segment": <name>, "size": <e.g. "40% of TAM">},
      {"icon": "👩‍💼", "segment": <name>, "size": <size>},
      {"icon": "🏢", "segment": <name>, "size": <size>}
    ]
  },
  "unit_economics": {
    "cac": <e.g. "₹2,400">,
    "ltv": <e.g. "₹18,000">,
    "ltv_cac": <e.g. "7.5x">,
    "gross_margin": <e.g. "68%">,
    "payback": <e.g. "4 months">,
    "churn": <e.g. "~5%/mo">,
    "note": <1 sentence on economics health>
  },
  "location_analysis": <2 sentences specific to the location>,
  "location_pros": [<pro 1>, <pro 2>, <pro 3>],
  "location_cons": [<con 1>, <con 2>],
  "competitors": [
    {"name": <name>, "type": <Indian/Global/Direct>, "weakness": <key weakness>, "your_edge": <how you beat them>},
    {"name": <name 2>, "type": ..., "weakness": ..., "your_edge": ...},
    {"name": <name 3>, "type": ..., "weakness": ..., "your_edge": ...},
    {"name": <name 4>, "type": ..., "weakness": ..., "your_edge": ...}
  ],
  "gtm_milestones": [
    {"time": "Month 1-2", "goal": <milestone>, "action": <specific action>},
    {"time": "Month 3-4", "goal": ..., "action": ...},
    {"time": "Month 5-6", "goal": ..., "action": ...},
    {"time": "Month 7-9", "goal": ..., "action": ...},
    {"time": "Month 10-12", "goal": ..., "action": ...}
  ],
  "funding_stages": [
    {"stage": "Bootstrapped", "amount": "₹0–25L", "current": <true if matches budget>},
    {"stage": "Pre-Seed", "amount": "₹25L–1Cr", "current": <true if matches>},
    {"stage": "Seed Round", "amount": "₹1Cr–5Cr", "current": false},
    {"stage": "Series A", "amount": "₹10Cr+", "current": false}
  ],
  "swot": {
    "strengths": [<3-4 short tags>],
    "weaknesses": [<2-3 short tags>],
    "opportunities": [<3-4 short tags>],
    "threats": [<2-3 short tags>]
  },
  "action_items": [
    {"icon": "🎯", "title": <action>, "detail": <specific advice>, "priority": <"P0 – Urgent"|"P1 – This Week"|"P2 – This Month">},
    {"icon": "💬", "title": ..., "detail": ..., "priority": ...},
    {"icon": "🔧", "title": ..., "detail": ..., "priority": ...},
    {"icon": "📣", "title": ..., "detail": ..., "priority": ...},
    {"icon": "💰", "title": ..., "detail": ..., "priority": ...}
  ]
}

Be specific, realistic, and use India-appropriate numbers (₹) where relevant."""


# ============================================================
# VIEWS
# ============================================================
@login_required(login_url='/users/login/')
def dashboard_home(request):
    return render(request, 'dashboard/dashboard.html', {
        'user': request.user
    })


import time

def call_gemini_multimodal(text_prompt, images, system_prompt, max_total_attempts=6):
    """
    Tries multiple Gemini models with auto-retry on 503/429 errors.
    
    Strategy:
    1. For each model, retry up to 3 times with exponential backoff (2s, 4s, 8s)
    2. If model still fails after 3 tries, move to next model
    3. If ALL models exhausted, raise last error
    """
    if client is None:
        raise Exception("Gemini API client not initialized. Check GEMINI_API_KEY in .env")

    # Build multimodal contents
    contents = [text_prompt]
    for img in images or []:
        if not img or not img.get('data'):
            continue
        try:
            header, b64 = img['data'].split(',', 1)
            mime = header.split(':')[1].split(';')[0]
            contents.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": b64
                }
            })
        except Exception as e:
            print(f"[Image parse skipped] {e}")
            continue

    # ✅ Model priority — less popular = more available capacity
    # We put 'lite' versions and '1.5' BEFORE the popular '2.0-flash'
    # because 2.0-flash gets overloaded first
    models_to_try = [
        "gemini-2.0-flash-lite",     # ✅ BEST CHOICE — less traffic, more capacity
        "gemini-1.5-flash-8b",       # Smallest, highest rate limit
        "gemini-1.5-flash",          # Old reliable
        "gemini-2.5-flash-lite",     # Newer lite
        "gemini-flash-latest",       # Auto-alias
        "gemini-2.0-flash",          # Popular (often overloaded)
        "gemini-2.5-flash",          # Newest (often overloaded)
        "gemini-1.5-pro",            # Pro fallback
    ]

    last_error = None
    
    for model_name in models_to_try:
        # Try each model up to 3 times
        for attempt in range(1, 4):
            try:
                print(f"[Trying: {model_name} | Attempt {attempt}/3]")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config={
                        "response_mime_type": "application/json",
                        "system_instruction": system_prompt
                    }
                )
                result = json.loads(response.text)
                print(f"[✅ Success: {model_name} on attempt {attempt}]")
                return result
                
            except Exception as e:
                error_msg = str(e)
                last_error = e
                
                # ✅ 503 (overloaded) or 429 (quota) → retry same model
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    if attempt < 3:
                        wait_time = 2 ** attempt  # 2s, 4s, 8s
                        print(f"[⏳ {model_name} overloaded. Waiting {wait_time}s before retry...]")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[⏭️  {model_name} still overloaded after 3 tries. Trying next model...]")
                        break
                
                elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                    if attempt < 3:
                        wait_time = 2 ** attempt
                        print(f"[⏳ {model_name} quota hit. Waiting {wait_time}s...]")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[⏭️  {model_name} quota exhausted. Trying next model...]")
                        break
                
                elif "404" in error_msg or "NOT_FOUND" in error_msg:
                    # 404 means model doesn't exist for this key — don't retry
                    print(f"[⏭️  {model_name} not available. Trying next model...]")
                    break
                
                else:
                    # Unknown error — don't retry, just fail
                    print(f"[❌ {model_name} unknown error: {error_msg[:200]}]")
                    raise e

    # All models + all retries exhausted
    raise Exception(
        f"All Gemini models are currently busy. Last error: {str(last_error)[:200]}. "
        f"Please try again in 1-2 minutes."
    )



@login_required
def ai_idea_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    # ✅ Check client BEFORE trying to use it
    if client is None:
        return JsonResponse({
            "error": "❌ Gemini API key not configured. Add GEMINI_API_KEY to your .env file and restart the server."
        }, status=503)

    try:
        data = json.loads(request.body)
        idea = (data.get('idea') or '').strip()
        location = (data.get('location') or '').strip()
        industry = data.get('industry') or 'Other'
        stage = data.get('stage') or 'idea'
        budget = data.get('budget') or 'bootstrap'
        team_size = data.get('team_size', 'Solo Founder')
        target_audience = data.get('target_audience', 'General Users')
        images = data.get('images', [])

        if not idea:
            return JsonResponse({"error": "No idea provided"}, status=400)

        text_prompt = f"""Startup Idea: {idea}
Location: {location}
Industry: {industry}
Current Stage: {stage}
Budget: {budget}
Target Audience: {target_audience}
Team Size: {team_size}

Return ONLY valid JSON matching the exact structure required. No markdown, no explanation."""

        # Cache key (user-scoped)
        safe_idea = re.sub(r'\W+', '_', idea)[:50]
        safe_location = re.sub(r'\W+', '_', location or "global")[:30]
        cache_key = f"ai:v1:{request.user.id}:{safe_idea}:{safe_location}"
        cached = cache.get(cache_key)

        if cached:
            print(f"[Cache hit] User {request.user.id}")
            request.session['ai_result'] = json.dumps(cached)
            request.session['idea'] = idea
            request.session.save()
            return JsonResponse(cached)

        # Call Gemini (with model fallback)
        result = call_gemini_multimodal(
            text_prompt=text_prompt,
            images=images,
            system_prompt=SYSTEM_PROMPT
        )

        # Cache 5 min
        cache.set(cache_key, result, timeout=300)

        # Save for PDF
        request.session['ai_result'] = json.dumps(result)
        request.session['idea'] = idea
        request.session.save()

        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON sent to server"}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": f"AI Error: {str(e)[:300]}"}, status=500)


@login_required
def export_pdf(request):
    data_raw = request.session.get('ai_result')
    idea = request.session.get('idea', "Startup Idea")

    if not data_raw:
        return HttpResponse(
            "❌ No AI report found. Please run an analysis first, then click export.",
            status=400
        )

    try:
        data = json.loads(data_raw)
    except json.JSONDecodeError:
        return HttpResponse("❌ Invalid report data in session.", status=400)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="validatorai_report.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    y = height - 50

    # HEADER
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, "🚀 ValidatorAI — Startup Report")
    y -= 30
    p.setFont("Helvetica", 11)
    p.drawString(50, y, f"Idea: {idea[:80]}")
    y -= 22

    score = data.get('score', 'N/A')
    verdict = data.get('verdict_label', 'N/A')
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, f"Viability Score: {score}/100   |   Verdict: {verdict}")
    y -= 30

    # GENERATED IMAGE
    try:
        image_prompt = f"{idea} startup business concept modern"
        img_url = f"https://image.pollinations.ai/prompt/{quote(image_prompt)}?width=512&height=512&seed=42&nologo=true"
        res = requests.get(img_url, timeout=15)
        if res.status_code == 200:
            img_bytes = io.BytesIO(res.content)
            if y < 220:
                p.showPage()
                y = height - 50
            p.drawImage(ImageReader(img_bytes), 50, y - 170, width=400, height=150)
            y -= 180
    except Exception as e:
        print(f"[PDF image error] {e}")

    # RISK CHART
    try:
        risks = data.get("risks_breakdown", [])
        if risks:
            labels = [r.get('label', '') for r in risks]
            values = [r.get('value', 0) for r in risks]
            colors = ['#f43f5e' if v >= 60 else '#f59e0b' if v >= 40 else '#22d3a0' for v in values]

            plt.figure(figsize=(6.5, 3))
            plt.bar(labels, values, color=colors)
            plt.title("Risk Profile", fontsize=11)
            plt.ylabel("Risk Level (%)", fontsize=9)
            plt.ylim(0, 100)
            plt.xticks(rotation=20, ha='right', fontsize=7)
            plt.tight_layout()

            chart_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(chart_file.name, dpi=120)
            plt.close()

            if y < 260:
                p.showPage()
                y = height - 50
            p.drawImage(chart_file.name, 50, y - 210, width=420, height=200)
            y -= 230
            try:
                os.remove(chart_file.name)
            except OSError:
                pass
    except Exception as e:
        print(f"[PDF chart error] {e}")

    def draw_section(title, content, y, indent=False):
        if not content:
            return y
        if y < 80:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, title)
        y -= 18
        p.setFont("Helvetica", 10)
        for line in textwrap.wrap(str(content), width=95):
            if y < 50:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 10)
            x = 60 if indent else 50
            p.drawString(x, y, line)
            y -= 13
        y -= 8
        return y

    # TEXT SECTIONS
    y = draw_section("📌 Summary", data.get("summary"), y)
    y = draw_section("📊 Market Size", data.get("market_size"), y)
    y = draw_section("📈 Growth Rate", data.get("growth_rate"), y)
    y = draw_section("💰 Year 1 MRR", data.get("mrr_yr1"), y)
    y = draw_section("⏳ Breakeven", data.get("breakeven"), y)

    mf = data.get("market_fit", {})
    y = draw_section(
        "🎯 Market Fit",
        f"{mf.get('score')}/10 — {mf.get('label', '')}\n{mf.get('description', '')}",
        y
    )

    ue = data.get("unit_economics", {})
    y = draw_section(
        "💵 Unit Economics",
        f"CAC: {ue.get('cac')}   |   LTV: {ue.get('ltv')}   |   LTV:CAC: {ue.get('ltv_cac')}\n"
        f"Margin: {ue.get('gross_margin')}   |   Payback: {ue.get('payback')}   |   Churn: {ue.get('churn')}\n"
        f"{ue.get('note', '')}",
        y
    )

    y = draw_section("📍 Location Feasibility", data.get("location_analysis"), y)
    y = draw_section("✅ Location Pros", "\n".join(f"• {x}" for x in data.get("location_pros", [])), y)
    y = draw_section("❌ Location Cons", "\n".join(f"• {x}" for x in data.get("location_cons", [])), y)

    # COMPETITORS
    if data.get("competitors"):
        if y < 200:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, "🏢 Competitor Landscape")
        y -= 18
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, y, "Competitor")
        p.drawString(180, y, "Weakness")
        p.drawString(370, y, "Your Edge")
        y -= 4
        p.line(50, y, 545, y)
        y -= 12
        p.setFont("Helvetica", 9)
        for c in data["competitors"]:
            if y < 50:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 9)
            p.drawString(50, y, str(c.get('name', ''))[:25])
            p.drawString(180, y, str(c.get('weakness', ''))[:32])
            p.drawString(370, y, str(c.get('your_edge', ''))[:28])
            y -= 13

    # GTM
    if data.get("gtm_milestones"):
        if y < 200:
            p.showPage()
            y = height - 50
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, "🗺️ Go-To-Market Roadmap")
        y -= 18
        p.setFont("Helvetica", 9)
        for m in data["gtm_milestones"]:
            if y < 60:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 9)
            line = f"[{m.get('time', '')}] {m.get('goal', '')} — {m.get('action', '')}"
            for wrap in textwrap.wrap(line, width=100):
                p.drawString(50, y, wrap)
                y -= 12
            y -= 4

    # SWOT
    swot = data.get("swot", {})
    if swot:
        swot_text = (
            "Strengths: " + ", ".join(swot.get("strengths", [])) + "\n" +
            "Weaknesses: " + ", ".join(swot.get("weaknesses", [])) + "\n" +
            "Opportunities: " + ", ".join(swot.get("opportunities", [])) + "\n" +
            "Threats: " + ", ".join(swot.get("threats", []))
        )
        y = draw_section("⚖️ SWOT Snapshot", swot_text, y)

    # ACTIONS
    if data.get("action_items"):
        items_text = "\n".join(
            f"{a.get('icon', '•')} {a.get('title', '')} [{a.get('priority', '')}]: {a.get('detail', '')}"
            for a in data["action_items"]
        )
        y = draw_section("✅ Action Plan", items_text, y)

    # FOOTER
    p.setFont("Helvetica-Oblique", 8)
    p.setFillColorRGB(0.5, 0.5, 0.5)
    p.drawString(50, 30, "Generated by ValidatorAI • Powered by Gemini")

    p.save()
    return response

# ============================================================
# LOCATION INTELLIGENCE (OpenStreetMap - Free, no API key)
# ============================================================
import requests
from django.core.cache import cache
import re
import time

GOOGLE_MAPS_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '').strip()


def geocode_location(query):
    """Convert location name to lat/lng using OpenStreetMap (free)."""
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
        print(f"[Geocode error] {e}")
    return None


def get_nearby_places(lat, lng, keyword='business', radius=2000):
    """Find nearby businesses using Overpass API (OpenStreetMap, free)."""
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:10];
        (
          node["shop"](around:{radius},{lat},{lng});
          node["amenity"~"restaurant|cafe|bank|hospital|school|pharmacy|marketplace"](around:{radius},{lat},{lng});
          way["shop"](around:{radius},{lat},{lng});
          way["amenity"~"restaurant|cafe|bank|hospital|school|pharmacy|marketplace"](around:{radius},{lat},{lng});
        );
        out body 20;
        """
        r = requests.post(overpass_url, data={'data': query}, timeout=15)
        data = r.json()
        results = []
        for elem in data.get('elements', [])[:20]:
            tags = elem.get('tags', {})
            name = tags.get('name') or tags.get('amenity', tags.get('shop', 'Business'))
            results.append({
                'name': name,
                'lat': elem.get('lat', 0),
                'lng': elem.get('lon', 0),
                'vicinity': tags.get('addr:street', ''),
                'source': 'openstreetmap'
            })
        return results
    except Exception as e:
        print(f"[Nearby places error] {e}")
        return []


def get_demand_indicators(lat, lng):
    """Estimate demand using OpenStreetMap data."""
    indicators = {
        'population_density': 50,
        'business_density': 0,
        'commercial_activity': 0,
        'accessibility': 60,
    }
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
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
        total_count = len(data.get('elements', []))
        indicators['business_density'] = min(100, total_count * 2)
        indicators['commercial_activity'] = min(100, total_count * 1.5)
    except Exception as e:
        print(f"[Demand indicators error] {e}")
    return indicators


def calculate_location_risk(lat, lng):
    """Calculate risk factors using geographic data."""
    risks = {
        'crime_risk': 35,
        'flood_risk': 15,
        'traffic_risk': 50,
        'regulatory_risk': 30,
    }
    try:
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:10];
        (
          way["waterway"~"river|stream"](around:5000,{lat},{lng});
          way["natural"="water"](around:5000,{lat},{lng});
        );
        out count;
        """
        r = requests.post(overpass_url, data={'data': query}, timeout=15)
        data = r.json()
        water_count = len(data.get('elements', []))
        risks['flood_risk'] = min(80, water_count * 10)
    except Exception as e:
        print(f"[Risk calculation error] {e}")
    return risks


@login_required
def location_intelligence(request):
    """
    GET /dashboard/location-intel/?location=Delhi&industry=restaurant
    Returns: geocoded location, nearby places, demand & risk indicators
    """
    location = request.GET.get('location', '').strip()
    industry = request.GET.get('industry', 'business')

    if not location:
        return JsonResponse({'error': 'Location parameter required'}, status=400)

    # Cache key (user-scoped)
    safe_loc = re.sub(r'\W+', '_', location)[:30]
    cache_key = f"loc:v1:{request.user.id}:{safe_loc}:{industry}"
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

    # 5. Overall score
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

