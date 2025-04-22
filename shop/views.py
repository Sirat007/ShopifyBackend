from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from .models import Product,Cart,CartItem ,Transaction
from .serializers import ProductSerializer,DetailedProductSerializer,CartSerializer,CartItemSerializer,SimpleCartSerializer,UserSerializer,CartCodeSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
import uuid
from decimal import Decimal
from django.shortcuts import get_object_or_404
import requests
from rest_framework.views import APIView
import stripe
from django.views.decorators.csrf import csrf_exempt


BASE_URL = settings.FRONTEND_BASE_URL

stripe.api_key=settings.STRIPE_SECRET_KEY
# Create your views here.

@api_view(["GET"])
def products(request):
    products = Product.objects.all()
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@api_view(["GET"])
def product_detail(request, slug):
    product = Product.objects.get(slug=slug)
    serializer = DetailedProductSerializer(product)
    return Response(serializer.data)

class CurrentUserCartCodeView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # cart = Cart.objects.get(cart_code=cart_code)
            cart = Cart.objects.get(user=request.user.id, paid=False)
            serializer = CartCodeSerializer(cart)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Cart.DoesNotExist:
            return Response({'cart_code': None}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def add_item(request):
    try:
        cart_code = request.data.get("cart_code")
        product_id = request.data.get("product_id")
        
        if not cart_code or not product_id:
            return Response(
                {"error": "Missing required fields: cart_code and product_id are required"}, 
                status=400
            )
            
        
        cart, created = Cart.objects.get_or_create(cart_code=cart_code,user=request.user)
        
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": f"Product with id {product_id} not found"}, status=404)
        
        
        cartitem, created = CartItem.objects.get_or_create(cart=cart, product=product)
        
        
        if not created:
            cartitem.quantity += 1
        else:
            cartitem.quantity = 1
            
        cartitem.save()
        
       
        serializer = CartItemSerializer(cartitem)
        return Response(
            {"data": serializer.data, "message": "CartItem created successfully"}, 
            status=201
        )
    
    except Exception as e:
        
        return Response({"error": str(e)}, status=400)
    
@api_view(['GET'])
def product_in_cart(request):
    cart_code = request.query_params.get("cart_code")
    product_id = request.query_params.get("product_id")

    try:
        cart = Cart.objects.get(cart_code=cart_code)
        product = Product.objects.get(id=product_id)
    except (Cart.DoesNotExist, Product.DoesNotExist):
        return Response({'error': 'Cart or product not found'}, status=404)

    product_exists_in_cart = CartItem.objects.filter(cart=cart, product=product).exists()

    return Response({'product_in_cart': product_exists_in_cart})

@api_view(['GET'])
def get_cart_stat(request):
    cart_code = request.query_params.get("cart_code")
    cart = Cart.objects.get(cart_code=cart_code, paid=False)
    serializer = SimpleCartSerializer(cart)
    return Response(serializer.data)

@api_view(['GET'])
def get_cart(request):
    cart_code = request.query_params.get("cart_code")
    cart = Cart.objects.get(cart_code=cart_code, paid=False)
    serializer = CartSerializer(cart)
    return Response(serializer.data)

@api_view(['PATCH'])
def update_quantity(request):
    try:
        cartitem_id = request.data.get("item_id")
        quantity = request.data.get("quantity")
        quantity = int(quantity)
        cartitem = CartItem.objects.get(id=cartitem_id)
        cartitem.quantity = quantity
        cartitem.save()
        serializer = CartItemSerializer(cartitem)
        return Response({"data": serializer.data, "message": "Cartitem updated successfully!"})
    except Exception as e:
        return Response({'error': str(e)}, status=400)
    

@api_view(['POST'])
def delete_cartitem(request):
   
    cartitem_id = request.data.get("item_id")

    if not cartitem_id:
        return Response({"error": "item_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        cartitem = CartItem.objects.get(id=cartitem_id)
        cartitem.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except CartItem.DoesNotExist:
        return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error deleting cart item: {e}") 
        return Response({"message": "Item deleted successfully"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_username(request):
    user = request.user
    return Response({"username": user.username})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_info(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response(serializer.data)






@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    try:
        tx_ref = str(uuid.uuid4())

        cart_code = request.data.get("cart_code")
        print(f"Received cart code: {cart_code}")  
        print(f"Received user: {request.user.id}") 

        cart = get_object_or_404(Cart, cart_code=cart_code, user=request.user)
        user = request.user

        amount = sum([item.quantity * item.product.price for item in cart.items.all()])

        tax = Decimal("5.00")  
        total_amount = amount + tax

        currency = "USD" 
        redirect_url = f"{BASE_URL}payment-status/"

        transaction = Transaction.objects.create(
            ref=tx_ref,
            cart=cart,
            amount=total_amount,
            currency=currency,
            user=user,
            status='pending'
        )
        
        flutterwave_payload = {
            "tx_ref": tx_ref,
            "amount": str(total_amount),
            "currency": currency,
            "redirect_url": redirect_url,
            "customer": {
                "email": user.email,
                "name": user.username,
                "phonenumber": user.phone
            },
            "customizations": {
                "title": "Shoppify Payment"
            }
        }
        
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                'https://api.flutterwave.com/v3/payments',
                json=flutterwave_payload,
                headers=headers
            )
            
            print(f"Flutterwave Response Status: {response.status_code}")
            print(f"Flutterwave Response Body: {response.json()}")

            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response(response.json(), status=response.status_code)
        
        except requests.exceptions.RequestException as e:
            print(f"Request Exception: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
def payment_callback(request):
    status = request.GET.get('status')
    tx_ref = request.GET.get('tx_ref')
    transaction_id = request.GET.get('transaction_id')

    user = request.user

    if status == 'successful':
       
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"
        }

        response = requests.get(f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify", headers=headers)
        response_data = response.json()

        if response_data['status'] == 'success':
            transaction = Transaction.objects.get(ref=tx_ref)

           
            if (response_data['data']['status'] == "successful"
                    and float(response_data['data']['amount']) == float(transaction.amount)
                    and response_data['data']['currency'] == transaction.currency):
              
                transaction.status = 'completed'
                transaction.save()

                cart = transaction.cart
                cart.paid = True
                cart.user = user
                cart.save()

                return Response({'message': 'Payment successful!', 'subMessage': 'You have successfully made payment'})
            else:
                
                return Response({'message': 'Payment verification failed.', 'subMessage': 'Your payment verification failed'})
        else:
            return Response({'message': 'Failed to verify transaction with Flutterwave.', 'submessgae': 'We could not verify the transaction'})
            
    else:
        return Response({'message': 'Payment was not successful.'}, status=400)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_paymentstripe(request):
    try:
        payment_id = str(uuid.uuid4())

        cart_code = request.data.get("cart_code")
        print(f"Received cart code: {cart_code}")  
        print(f"Received user: {request.user.id}") 

        cart = get_object_or_404(Cart, cart_code=cart_code, user=request.user)
        user = request.user

        amount = sum([item.quantity * item.product.price for item in cart.items.all()])

        tax = Decimal("5.00")  
        total_amount = amount + tax

        
        stripe_amount = int(total_amount * 100)
        currency = "usd"  
        
        
        transaction = Transaction.objects.create(
            ref=payment_id,
            cart=cart,
            amount=total_amount,
            currency=currency,
            user=user,
            status='pending'
        )
        
        
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency,
                        'product_data': {
                            'name': 'Shoppify Order',
                        },
                        'unit_amount': stripe_amount,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f"{BASE_URL}payment-status?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{BASE_URL}payment-status?canceled=true",
                client_reference_id=payment_id,
                customer_email=user.email,
                metadata={
                    'cart_code': cart_code,
                    'user_id': str(user.id)
                }
            )
            
            print(f"Stripe Session Created: {checkout_session.id}")
            
            # Return the checkout session ID to the frontend
            return Response({
                'sessionId': checkout_session.id,
                'url': checkout_session.url
            }, status=status.HTTP_200_OK)
            
        except stripe.error.StripeError as e:
            print(f"Stripe Error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def payment_success(request):
    try:
        session_id = request.GET.get('session_id')
        print(session_id)
        if not session_id:
            return Response({'message': 'No session ID provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Retrieve the checkout session to verify payment
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == 'paid':
            # Get the transaction reference from the client_reference_id
            payment_id = checkout_session.client_reference_id
            
            try:
                # Update transaction status
                transaction = Transaction.objects.get(ref=payment_id)
                transaction.status = 'completed'
                transaction.save()
                
                # Update cart status
                cart = transaction.cart
                cart.paid = True
                cart.save()
                
                return Response({
                    'message': 'Payment successful!', 
                    'subMessage': 'You have successfully made payment'
                }, status=status.HTTP_200_OK)
                
            except Transaction.DoesNotExist:
                return Response({
                    'message': 'Transaction not found',
                    'subMessage': 'We could not find your transaction record'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'message': 'Payment not completed',
                'subMessage': 'Your payment was not completed successfully'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except stripe.error.StripeError as e:
        return Response({
            'message': 'Stripe verification error',
            'subMessage': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'message': 'Something went wrong',
            'subMessage': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def payment_canceled(request):
    return Response({
        'message': 'Payment was canceled',
        'subMessage': 'Your payment process was canceled'
    }, status=status.HTTP_400_BAD_REQUEST)

# Webhook handler for asynchronous payment events (optional but recommended)
@api_view(['POST'])
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        
        # Handle the checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Make sure it's a payment/checkout event
            if session.payment_status == 'paid':
                payment_id = session.client_reference_id
                
                # Update transaction status
                try:
                    transaction = Transaction.objects.get(ref=payment_id)
                    
                    # Only update if not already completed (to prevent duplicates)
                    if transaction.status != 'completed':
                        transaction.status = 'completed'
                        transaction.save()
                        
                        # Update cart status
                        cart = transaction.cart
                        cart.paid = True
                        cart.save()
                        
                except Transaction.DoesNotExist:
                    print(f"Transaction with reference {payment_id} not found")
                
        return Response({'status': 'success'}, status=status.HTTP_200_OK)
        
    except ValueError as e:
        # Invalid payload
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)