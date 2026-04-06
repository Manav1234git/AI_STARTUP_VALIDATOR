from django.shortcuts import render

# Create your views here.
def analysis(request):
    return render(request, "analysis/analysis_result.html")