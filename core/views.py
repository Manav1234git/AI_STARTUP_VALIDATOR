from django.shortcuts import render

def home(request):
    return render(request, "core/index.html")

def about(request):
    return render(request, "core/about.html")


def demo(request):
    return render(request ,"core/demo.html")

# Example product database
# PRODUCTS = [
#     {"name": "Smartphone", "category": "tech", "description": "Latest mobile devices", "image": "https://via.placeholder.com/200"},
#     {"name": "Laptop", "category": "tech", "description": "High-performance laptops", "image": "https://via.placeholder.com/200"},
#     {"name": "Organic Honey", "category": "food", "description": "Natural honey from farms", "image": "https://via.placeholder.com/200"},
#     {"name": "Headphones", "category": "tech", "description": "Noise-cancelling headphones", "image": "https://via.placeholder.com/200"},
#     {"name": "Protein Powder", "category": "health", "description": "Muscle building supplements", "image": "https://via.placeholder.com/200"},
#     # Add more products here
# ]

# def products(request):
#     idea = request.GET.get('idea', '').lower()  # get idea from query param
#     if idea:
#         # Simple filtering: show products if idea word matches category or name
#         filtered_products = [p for p in PRODUCTS if idea in p['name'].lower() or idea in p['category'].lower()]
#     else:
#         filtered_products = PRODUCTS  # show all if no idea provided

#     return render(request, 'product.html', {'products': filtered_products, 'idea': idea})