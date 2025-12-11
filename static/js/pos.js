// --- static/js/pos.js ---

let cart = [];
const cartItemsContainer = document.getElementById('cart-items');
const subtotalSpan = document.getElementById('subtotal');
const grandTotalSpan = document.getElementById('grand-total');

// Helper function to format currency (client-side for display)
function formatCurrency(value) {
    // Basic client-side INR formatting
    return `₹ ${parseFloat(value).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
}

// Function to add a product to the cart
function addToCart(productElement) {
    const id = parseInt(productElement.getAttribute('data-id'));
    const name = productElement.getAttribute('data-name');
    const price = parseFloat(productElement.getAttribute('data-price'));

    const existingItem = cart.find(item => item.id === id);

    if (existingItem) {
        existingItem.qty += 1;
    } else {
        cart.push({ id, name, price, qty: 1 });
    }
    renderCart();
}

// Renders the cart table and updates totals
function renderCart() {
    if (!cartItemsContainer) return;

    cartItemsContainer.innerHTML = '';
    let subtotal = 0;

    cart.forEach((item, index) => {
        const itemTotal = item.price * item.qty;
        subtotal += itemTotal;
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.name}</td>
            <td style="text-align: center;">
                <input type="number" value="${item.qty}" min="1" 
                       onchange="updateCartQty(${index}, this.value)" style="width: 50px;">
            </td>
            <td>${formatCurrency(item.price)}</td>
            <td>${formatCurrency(itemTotal)}</td>
            <td><button onclick="removeFromCart(${index})" class="btn-remove">X</button></td>
        `;
        cartItemsContainer.appendChild(row);
    });

    const grandTotal = subtotal; 

    subtotalSpan.textContent = formatCurrency(subtotal);
    grandTotalSpan.textContent = formatCurrency(grandTotal);
}

// Update quantity from input field
function updateCartQty(index, newQty) {
    newQty = parseInt(newQty);
    if (newQty > 0) {
        cart[index].qty = newQty;
    } else {
        removeFromCart(index);
    }
    renderCart();
}

// Remove item from cart
function removeFromCart(index) {
    cart.splice(index, 1);
    renderCart();
}

// Function to handle both QR code scanning and regular text search
function handleScanOrSearch(event) {
    const input = event.target;
    const value = input.value.trim();
    
    // Process as QR scan if it matches the prefix and Enter is pressed (key code 13)
    if (value.startsWith('POS_PRODUCT_') && (event.keyCode === 13 || event.type === 'change')) {
        const productId = parseInt(value.replace('POS_PRODUCT_', ''));
        const productElement = document.querySelector(`.product-card[data-id="${productId}"]`);
        
        if (productElement) {
            addToCart(productElement);
            input.value = ''; // Clear input immediately
        } else {
            alert("Product not found with this QR code.");
        }
        
    } else {
        // Fallback to regular filtering
        filterProductsByName(value);
    }
}

// Filters products by name
function filterProductsByName(searchInput) {
    searchInput = searchInput.toLowerCase();
    const cards = document.querySelectorAll('.product-card');

    cards.forEach(card => {
        const name = card.getAttribute('data-name').toLowerCase();
        card.style.display = name.includes(searchInput) ? 'block' : 'none';
    });
}

// New function to quickly add a customer from the billing screen
function quickAddCustomer() {
    const name = document.getElementById('new-cust-name').value;
    const phone = document.getElementById('new-cust-phone').value;

    if (!name || !phone) {
        alert("Name and Phone are required.");
        return;
    }

    fetch('/add_customer_quick', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, phone })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`Customer ${name} added and selected.`);
            
            // Add new customer to the select dropdown dynamically
            const select = document.getElementById('customer-select');
            const newOption = new Option(`${data.name} (${data.phone})`, data.customer_id, true, true);
            select.add(newOption);
            
            // Hide the form and clear inputs
            document.getElementById('new-customer-form').style.display = 'none';
            document.getElementById('new-cust-name').value = '';
            document.getElementById('new-cust-phone').value = '';
            
        } else {
            alert(`Error adding customer: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("An error occurred while saving the new customer.");
    });
}

// Handles the checkout process (sends data to Flask route)
function checkout(paymentMethod) {
    if (cart.length === 0) {
        alert("The cart is empty. Please add items to complete a sale.");
        return;
    }

    const customerSelect = document.getElementById('customer-select');
    const customerId = customerSelect.value ? parseInt(customerSelect.value) : null;

    const transactionData = {
        cart: cart.map(item => ({
            id: item.id,
            qty: item.qty,
            name: item.name,
            price: item.price
        })),
        customer_id: customerId,
        payment_method: paymentMethod
    };

    fetch('/checkout', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(transactionData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert(`Sale successful! Payment: ${paymentMethod}. Transaction ID: ${data.transaction_id}`);
            
            window.open(`/receipt/${data.transaction_id}`, '_blank');
            
            cart = [];
            renderCart();
            document.getElementById('customer-select').value = '';
            
        } else {
             alert(`Error processing sale: ${data.message}`);
        }
    })
    .catch((error) => {
        console.error('Error:', error);
        alert(`An error occurred: ${error.message}`);
    });
}

document.addEventListener('DOMContentLoaded', renderCart);