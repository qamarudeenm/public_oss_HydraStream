const PRODUCTS = [
    { id: 'prod_001', name: 'Aero-Flow Runners', price: 189.99, image: 'assets/product_shoes_premium_1774700211718.png' },
    { id: 'prod_002', name: 'Nexus Chrono v2', price: 449.00, image: 'assets/product_watch_premium_1774700266752.png' },
    { id: 'prod_003', name: 'Zenith ANC Headphones', price: 299.50, image: 'assets/product_headphones_premium_1774700484579.png' }
];

let cart = [];

// Navigation
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
    
    document.querySelectorAll('.nav-item').forEach(item => {
        if (item.dataset.page === pageId) item.classList.add('active');
        else item.classList.remove('active');
    });

    // Track page view
    if (window.NexusTracker) {
        NexusTracker.track('page_view', { page: pageId });
    }
}

document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        showPage(item.dataset.page);
    });
});

// Render Products
function renderProducts() {
    const list = document.getElementById('product-list');
    list.innerHTML = PRODUCTS.map(product => `
        <div class="product-card" data-product-id="${product.id}">
            <div class="product-image">
                <img src="${product.image}" alt="${product.name}">
            </div>
            <div class="product-info">
                <h3>${product.name}</h3>
                <p class="product-price">$${product.price.toFixed(2)}</p>
                <button class="btn-primary add-to-cart" data-id="${product.id}">Add to Cart</button>
            </div>
        </div>
    `).join('');

    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', () => addToCart(btn.dataset.id));
    });
}

function addToCart(productId) {
    const product = PRODUCTS.find(p => p.id === productId);
    cart.push(product);
    updateCart();
    
    // Track cart action
    if (window.NexusTracker) {
        NexusTracker.track('add_to_cart', { 
            product_id: productId, 
            product_name: product.name,
            price: product.price
        });
    }
}

function updateCart() {
    document.getElementById('cart-count').innerText = cart.length;
    
    const cartItems = document.getElementById('cart-items');
    if (cart.length === 0) {
        cartItems.innerHTML = '<p>Your cart is empty.</p>';
    } else {
        cartItems.innerHTML = cart.map((item, index) => `
            <div class="cart-item">
                <div class="cart-item-info">
                    <h4>${item.name}</h4>
                    <span class="product-price">$${item.price.toFixed(2)}</span>
                </div>
                <button class="btn-secondary remove-from-cart" data-index="${index}">Remove</button>
            </div>
        `).join('');
    }

    const subtotal = cart.reduce((sum, item) => sum + item.price, 0);
    document.getElementById('subtotal').innerText = `$${subtotal.toFixed(2)}`;
    document.getElementById('total').innerText = `$${subtotal.toFixed(2)}`;

    document.querySelectorAll('.remove-from-cart').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = btn.dataset.index;
            const removed = cart.splice(index, 1)[0];
            updateCart();
            NexusTracker.track('remove_from_cart', { product_id: removed.id });
        });
    });
}

// Checkout Logic
document.getElementById('checkout-btn').addEventListener('click', () => {
    if (cart.length === 0) return alert('Cart is empty!');
    showPage('checkout');
    NexusTracker.track('checkout_start', { cart_size: cart.length, total: cart.reduce((s, i) => s + i.price, 0) });
});

document.getElementById('shipping-form').addEventListener('submit', (e) => {
    e.preventDefault();
    document.getElementById('step-info').classList.add('hidden');
    document.getElementById('step-payment').classList.remove('hidden');
    NexusTracker.track('checkout_step', { step: 'payment' });
});

document.getElementById('complete-purchase').addEventListener('click', () => {
    showPage('status-success');
    NexusTracker.track('purchase_success', { order_id: 'NX-' + Math.floor(Math.random() * 1000000), total: cart.reduce((s, i) => s + i.price, 0) });
    cart = [];
    updateCart();
});

document.getElementById('fail-purchase').addEventListener('click', () => {
    showPage('status-failure');
    NexusTracker.track('purchase_failed', { reason: 'insufficient_funds' });
});

document.getElementById('retry-payment').addEventListener('click', () => {
    showPage('checkout');
    document.getElementById('step-info').classList.add('hidden');
    document.getElementById('step-payment').classList.remove('hidden');
    NexusTracker.track('retry_payment', {});
});

// Initialize
renderProducts();
showPage('home');
console.log('Nexus Market Initialized');
