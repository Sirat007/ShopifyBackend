from django.urls import path

from .views import CurrentUserCartCodeView,payment_callback
from . import views

urlpatterns = [
    path("products", views.products, name="products"),
    path("product_detail/<slug:slug>", views.product_detail, name="product_detail"),
    path("add_item/", views.add_item, name="add_item"),
    path("product_in_cart", views.product_in_cart, name="product_in_cart"),
    path("get_cart_stat", views.get_cart_stat, name="get_cart_stat"),
    path("get_cart", views.get_cart, name="get_cart"),
    path("update_quantity/",views.update_quantity,name="update_quantity"),
    path("delete_cartitem/",views.delete_cartitem,name="delete_cartitem"),
    path("get_username/",views.get_username,name="get_username"),
    path("user_info",views.user_info,name="user_info"),
    path("initiate_payment/",views.initiate_payment,name="initiate_payment"),
    path('current-user/cart-code/', CurrentUserCartCodeView.as_view(), name='current-user-cart-code'),
    path("payment_callback/",views.payment_callback,name="payment_callback"),
    path('payments/initiate/', views.initiate_paymentstripe, name='initiate_payment'),
    path('payments/success/', views.payment_success, name='payment_success'),
    path('payments/canceled/', views.payment_canceled, name='payment_canceled'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
]
