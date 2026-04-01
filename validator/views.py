from django.shortcuts import render
from analysis.services import run_analysis
from reports.services import generate_report

def validate_idea(request):
    if request.method == "POST":
        idea = request.POST.get("idea")
        audience = request.POST.get("audience")
        problem = request.POST.get("problem")

        # Step 1: Analysis
        analysis_data = run_analysis(idea, audience, problem)

        # Step 2: Final Report
        report = generate_report(analysis_data)

        return render(request, "reports/result.html", {"report": report})

    return render(request, "core/index.html")