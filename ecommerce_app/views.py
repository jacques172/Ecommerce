from django.shortcuts import render, HttpResponse, redirect, \
    get_object_or_404, reverse
from django.contrib import messages

from django.conf import settings
from decimal import Decimal
from paypal.standard.forms import PayPalPaymentsForm

from django.views.decorators.csrf import csrf_exempt

from .models import Product, Order, LineItem
from .forms import CartForm, CheckoutForm
from . import cart
from django.core.mail import send_mail

from django.core.paginator import Paginator
# Create your views here.



from .models import Product

def index(request):
    all_products = Product.objects.all()

    # Retrieve the search query from the request's GET parameters
    query = request.GET.get('query')

    # Filter the products based on the search query
    if query:
        all_products = all_products.filter(name__icontains=query)

    # Retrieve the selected category from the request's GET parameters
    category = request.GET.get('category')

    # Filter the products based on the selected category
    if category:
        all_products = all_products.filter(categories__name=category)

    # Paginate the products to display only three products per page
    paginator = Paginator(all_products, 3)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "ecommerce_app/store.html", {
        'page_obj': page_obj,
        'query': query,
    })




def show_product(request, product_id, product_slug):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        form = CartForm(request, request.POST)
        if form.is_valid():
            request.form_data = form.cleaned_data
            cart.add_item_to_cart(request)
            return redirect('show_cart')

    form = CartForm(request, initial={'product_id': product.id})
    return render(request, 'ecommerce_app/product_detail.html', {
                                            'product': product,
                                            'form': form,
                                            })


def show_cart(request):

    if request.method == 'POST':
        if request.POST.get('submit') == 'Update':
            cart.update_item(request)
        if request.POST.get('submit') == 'Remove':
            cart.remove_item(request)
    all_products = Product.objects.all()
    cart_items = cart.get_all_cart_items(request)
    cart_subtotal = cart.subtotal(request)
    return render(request, 'ecommerce_app/cart.html', {
                                            'cart_items': cart_items,
                                            'cart_subtotal': cart_subtotal,
                                            'all_products': all_products
                                            })


def checkout(request):
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            o = Order(
                name = cleaned_data.get('name'),
                email = cleaned_data.get('email'),
                postal_code = cleaned_data.get('postal_code'),
                address = cleaned_data.get('address'),
            )
            o.save()

            all_items = cart.get_all_cart_items(request)
            for cart_item in all_items:
                li = LineItem(
                    product_id = cart_item.product_id,
                    price = cart_item.price,
                    quantity = cart_item.quantity,
                    order_id = o.id
                )

                li.save()

            cart.clear(request)

            request.session['order_id'] = o.id
            

            messages.add_message(request, messages.INFO, 'Order Placed!')
            return redirect('process_payment')


    else:
        form = CheckoutForm()
        return render(request, 'ecommerce_app/checkout.html', {'form': form})

# ...

def process_payment(request):
    order_id = request.session.get('order_id')
    order = get_object_or_404(Order, id=order_id)
    host = request.get_host()

    # Convert the amount to Decimal before quantizing
    amount = Decimal(order.total_cost()).quantize(Decimal('.01'))

    paypal_dict = {
        'business': settings.PAYPAL_RECEIVER_EMAIL,
        'amount': str(amount),
        'item_name': 'Order {}'.format(order.id),
        'invoice': str(order.id),
        'currency_code': 'USD',
        'notify_url': 'http://{}{}'.format(host, reverse('paypal-ipn')),
        'return_url': 'http://{}{}'.format(host, reverse('payment_done')),
        'cancel_return': 'http://{}{}'.format(host, reverse('payment_cancelled')),
    }

    form = PayPalPaymentsForm(initial=paypal_dict)
    return render(request, 'ecommerce_app/process_payment.html', {'order': order, 'form': form})


@csrf_exempt
def payment_done(request):
    order_id = request.session.get('order_id')
    order = get_object_or_404(Order, id=order_id)
    user_email = order.email

    # send email to user
    subject = 'Order Confirmation'
    message = f'Thank you for your order. Your order ID is {order.id}.'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]
    send_mail(subject, message, from_email, recipient_list)

     # send email notification to yourself
    subject = 'New Order'
    message = f'A new order has been placed. Order ID: {order.id}.'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['asinyojacques17@gmail.com']
    send_mail(subject, message, from_email, recipient_list)
    return render(request, 'ecommerce_app/payment_done.html')


@csrf_exempt
def payment_canceled(request):
    return render(request, 'ecommerce_app/payment_cancelled.html')