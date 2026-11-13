const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? '' 
  : '';

let cartItems = []; // [{ sku_id, quantity }]
let activeCoupon = null;
let activeShippingMethod = 'standard';

// DOM Elements
const productsGrid = document.getElementById('productsGrid');
const cartCountBadge = document.getElementById('cartCountBadge');
const cartTotalPreview = document.getElementById('cartTotalPreview');
const cartDrawerCount = document.getElementById('cartDrawerCount');
const cartItemsContainer = document.getElementById('cartItemsContainer');

// Cart Summary Elements
const couponInput = document.getElementById('couponInput');
const applyCouponBtn = document.getElementById('applyCouponBtn');
const sumSubtotal = document.getElementById('sumSubtotal');
const sumDiscountRow = document.getElementById('sumDiscountRow');
const appliedCouponCode = document.getElementById('appliedCouponCode');
const sumDiscount = document.getElementById('sumDiscount');
const sumShipping = document.getElementById('sumShipping');
const sumTax = document.getElementById('sumTax');
const sumGrandTotal = document.getElementById('sumGrandTotal');

// Drawer & Modals
const cartBackdrop = document.getElementById('cartBackdrop');
const openCartBtn = document.getElementById('openCartBtn');
const closeCartBtn = document.getElementById('closeCartBtn');
const proceedCheckoutBtn = document.getElementById('proceedCheckoutBtn');

const checkoutModal = document.getElementById('checkoutModal');
const closeCheckoutBtn = document.getElementById('closeCheckoutBtn');
const cancelCheckoutBtn = document.getElementById('cancelCheckoutBtn');
const checkoutForm = document.getElementById('checkoutForm');

const invoiceModal = document.getElementById('invoiceModal');
const closeInvoiceBtn = document.getElementById('closeInvoiceBtn');
const closeInvoiceModalBtn = document.getElementById('closeInvoiceModalBtn');
const invoiceOrderNum = document.getElementById('invoiceOrderNum');
const invoiceBody = document.getElementById('invoiceBody');

// Merchant Elements
const ordersTableBody = document.getElementById('ordersTableBody');
const refreshOrdersBtn = document.getElementById('refreshOrdersBtn');
const kpiGrossRev = document.getElementById('kpiGrossRev');
const kpiOrderCount = document.getElementById('kpiOrderCount');
const kpiLowStock = document.getElementById('kpiLowStock');

// Navigation Tabs
const navBtns = document.querySelectorAll('.nav-btn');
const viewPanels = document.querySelectorAll('.view-panel');

navBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    navBtns.forEach(b => b.classList.remove('active'));
    viewPanels.forEach(p => p.classList.remove('active'));

    btn.classList.add('active');
    const view = btn.dataset.view;

    if (view === 'storefront') {
      document.getElementById('viewStorefront').classList.add('active');
      loadProducts();
    } else if (view === 'orders') {
      document.getElementById('viewOrders').classList.add('active');
      loadMerchantOrders();
      loadMerchantKPIs();
    }
  });
});

// Load Product Catalog
async function loadProducts() {
  try {
    const res = await fetch(`${API_BASE}/api/products`);
    const data = await res.json();
    renderProducts(data.products);
  } catch (err) {
    productsGrid.innerHTML = `<p class="text-crimson">Failed to load merchandise catalog.</p>`;
  }
}

function renderProducts(products) {
  if (!products || products.length === 0) {
    productsGrid.innerHTML = `<p class="text-muted">No merchandise available.</p>`;
    return;
  }

  productsGrid.innerHTML = products.map(p => {
    const defaultVariant = p.variants[0] || {};
    const optionsHtml = p.variants.map(v => `
      <option value="${v.id}" data-price="${v.price}" data-stock="${v.stock_quantity}">
        ${escapeHtml(v.variant_name)} — $${v.price.toFixed(2)} (${v.stock_quantity} in stock)
      </option>
    `).join('');

    return `
      <div class="product-card" id="card-${p.id}">
        <span class="prod-category">${p.category}</span>
        <div>
          <h3 class="prod-title">${escapeHtml(p.title)}</h3>
          <p class="prod-desc" style="margin-top: 0.35rem;">${escapeHtml(p.description)}</p>
        </div>
        <div class="variant-picker">
          <label>Select Variant / SKU</label>
          <select id="select-${p.id}" onchange="updateCardPrice('${p.id}')">
            ${optionsHtml}
          </select>
        </div>
        <div class="card-foot">
          <span class="prod-price" id="price-${p.id}">$${(defaultVariant.price || p.base_price).toFixed(2)}</span>
          <button class="btn btn-gold" onclick="addToCart('${p.id}')">+ Add to Bag</button>
        </div>
      </div>
    `;
  }).join('');
}

window.updateCardPrice = function(prodId) {
  const select = document.getElementById(`select-${prodId}`);
  const opt = select.options[select.selectedIndex];
  const price = parseFloat(opt.dataset.price);
  document.getElementById(`price-${prodId}`).textContent = `$${price.toFixed(2)}`;
};

// Add to Cart
window.addToCart = function(prodId) {
  const select = document.getElementById(`select-${prodId}`);
  const skuId = select.value;
  const existing = cartItems.find(i => i.sku_id === skuId);

  if (existing) {
    existing.quantity += 1;
  } else {
    cartItems.push({ sku_id: skuId, quantity: 1 });
  }

  updateCartState();
  openCart();
};

// Update Cart State & Calculations
async function updateCartState() {
  if (cartItems.length === 0) {
    cartCountBadge.textContent = '0';
    cartDrawerCount.textContent = '0';
    cartTotalPreview.textContent = '$0.00';
    cartItemsContainer.innerHTML = `<p class="text-muted text-center" style="padding: 2.5rem 0;">Your shopping bag is empty.</p>`;
    sumSubtotal.textContent = '$0.00';
    sumShipping.textContent = '$0.00';
    sumTax.textContent = '$0.00';
    sumGrandTotal.textContent = '$0.00';
    sumDiscountRow.style.display = 'none';
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/cart/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: cartItems,
        shipping_method: activeShippingMethod,
        coupon_code: activeCoupon
      })
    });

    const data = await res.json();

    cartCountBadge.textContent = data.item_count;
    cartDrawerCount.textContent = data.item_count;
    cartTotalPreview.textContent = `$${data.grand_total.toFixed(2)}`;

    sumSubtotal.textContent = `$${data.subtotal.toFixed(2)}`;
    sumShipping.textContent = `$${data.shipping_cost.toFixed(2)}`;
    sumTax.textContent = `$${data.sales_tax.toFixed(2)}`;
    sumGrandTotal.textContent = `$${data.grand_total.toFixed(2)}`;

    if (data.discount_amount > 0 && data.applied_coupon) {
      sumDiscountRow.style.display = 'flex';
      appliedCouponCode.textContent = data.applied_coupon;
      sumDiscount.textContent = `-$${data.discount_amount.toFixed(2)}`;
    } else {
      sumDiscountRow.style.display = 'none';
    }

    // Render items list
    cartItemsContainer.innerHTML = data.items_detail.map(item => `
      <div class="cart-item-row">
        <div>
          <div class="cart-item-title">${escapeHtml(item.product_title)}</div>
          <div class="cart-item-sub">${escapeHtml(item.variant_name)} · SKU: ${item.sku}</div>
          <div style="font-family: var(--font-mono); font-size: 0.82rem; color: var(--gold); margin-top: 0.2rem;">
            $${item.unit_price.toFixed(2)} ea
          </div>
        </div>
        <div class="cart-qty-ctrl">
          <button class="btn-qty" onclick="changeQty('${item.sku_id}', -1)">-</button>
          <span>${item.quantity}</span>
          <button class="btn-qty" onclick="changeQty('${item.sku_id}', 1)">+</button>
        </div>
      </div>
    `).join('');

  } catch (err) {
    console.error(err);
  }
}

window.changeQty = function(skuId, delta) {
  const item = cartItems.find(i => i.sku_id === skuId);
  if (!item) return;

  item.quantity += delta;
  if (item.quantity <= 0) {
    cartItems = cartItems.filter(i => i.sku_id !== skuId);
  }
  updateCartState();
};

// Coupon Handler
applyCouponBtn.addEventListener('click', () => {
  const code = couponInput.value.trim();
  if (code) {
    activeCoupon = code;
    updateCartState();
  }
});

// Cart Drawer Open / Close
function openCart() {
  cartBackdrop.classList.add('open');
}
function closeCart() {
  cartBackdrop.classList.remove('open');
}
openCartBtn.addEventListener('click', openCart);
closeCartBtn.addEventListener('click', closeCart);

// Checkout Modal
proceedCheckoutBtn.addEventListener('click', () => {
  if (cartItems.length === 0) {
    alert('Your cart is empty.');
    return;
  }
  closeCart();
  checkoutModal.classList.add('open');
});

function closeCheckout() {
  checkoutModal.classList.remove('open');
}
closeCheckoutBtn.addEventListener('click', closeCheckout);
cancelCheckoutBtn.addEventListener('click', closeCheckout);

checkoutForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const payload = {
    customer_name: document.getElementById('custName').value.trim(),
    customer_email: document.getElementById('custEmail').value.trim(),
    shipping_address: document.getElementById('custAddress').value.trim(),
    shipping_method: document.getElementById('custShipping').value,
    coupon_code: activeCoupon,
    items: cartItems
  };

  try {
    const res = await fetch(`${API_BASE}/api/orders/checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Checkout Error: ${err.detail}`);
      return;
    }

    const order = await res.json();
    closeCheckout();
    cartItems = [];
    activeCoupon = null;
    couponInput.value = '';
    updateCartState();
    loadProducts(); // refresh stock numbers

    alert(`🎉 Order ${order.order_number} confirmed! Total charged: $${order.grand_total.toFixed(2)} USD.`);
  } catch (err) {
    alert('Payment checkout network error');
  }
});

// Merchant Orders Desk
async function loadMerchantOrders() {
  try {
    const res = await fetch(`${API_BASE}/api/orders`);
    const data = await res.json();
    renderOrders(data.orders);
  } catch (err) {
    ordersTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-crimson">Failed to load orders</td></tr>`;
  }
}

function renderOrders(orders) {
  if (!orders || orders.length === 0) {
    ordersTableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding: 2.5rem;">No orders registered in system.</td></tr>`;
    return;
  }

  ordersTableBody.innerHTML = orders.map(o => {
    const badgeClass = `badge-${o.status.toLowerCase()}`;
    let actions = `<button class="btn btn-secondary btn-sm" onclick="viewInvoice('${o.id}')">Invoice</button>`;

    if (o.status === 'PAID') {
      actions += ` <button class="btn btn-secondary btn-sm" onclick="setOrderStatus('${o.id}', 'PROCESSING')">Process</button>`;
      actions += ` <button class="btn btn-secondary btn-sm" style="color: var(--crimson);" onclick="setOrderStatus('${o.id}', 'CANCELLED')">Cancel</button>`;
    } else if (o.status === 'PROCESSING') {
      actions += ` <button class="btn btn-gold btn-sm" onclick="setOrderStatus('${o.id}', 'SHIPPED')">Ship</button>`;
    } else if (o.status === 'SHIPPED') {
      actions += ` <button class="btn btn-gold btn-sm" onclick="setOrderStatus('${o.id}', 'DELIVERED')">Deliver</button>`;
    }

    return `
      <tr>
        <td style="font-family: var(--font-mono); font-weight: 700; color: var(--gold);">${o.order_number}</td>
        <td style="font-size: 0.8rem; color: var(--text-muted);">${new Date(o.created_at).toLocaleDateString()}</td>
        <td>
          <div style="font-weight: 600;">${escapeHtml(o.customer_name)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(o.customer_email)}</div>
        </td>
        <td style="font-family: var(--font-mono);">$${o.subtotal.toFixed(2)}</td>
        <td style="font-family: var(--font-mono); color: var(--emerald);">${o.discount_amount > 0 ? `-$${o.discount_amount.toFixed(2)}` : '—'}</td>
        <td style="font-family: var(--font-mono); font-weight: 700; color: #fff;">$${o.grand_total.toFixed(2)}</td>
        <td><span class="badge ${badgeClass}">${o.status}</span></td>
        <td>${actions}</td>
      </tr>
    `;
  }).join('');
}

window.setOrderStatus = async function(orderId, targetStatus) {
  try {
    const res = await fetch(`${API_BASE}/api/orders/${orderId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: targetStatus })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Status transition error: ${err.detail}`);
      return;
    }

    loadMerchantOrders();
    loadMerchantKPIs();
    loadProducts();
  } catch (err) {
    alert('Failed to update status');
  }
};

window.viewInvoice = async function(orderId) {
  try {
    const res = await fetch(`${API_BASE}/api/orders/${orderId}`);
    if (!res.ok) return;
    const o = await res.json();

    invoiceOrderNum.textContent = `Invoice ${o.order_number}`;

    const itemsHtml = o.items.map(i => `
      <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 0.5rem 0; font-size: 0.85rem;">
        <div>
          <strong>${escapeHtml(i.product_title)}</strong> (${escapeHtml(i.variant_name)})<br>
          <span style="font-size: 0.75rem; color: var(--text-muted);">SKU: ${i.sku} | Qty: ${i.quantity} × $${i.unit_price.toFixed(2)}</span>
        </div>
        <div style="font-family: var(--font-mono); font-weight: 600;">$${i.line_total.toFixed(2)}</div>
      </div>
    `).join('');

    invoiceBody.innerHTML = `
      <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">
        Customer: <strong style="color: #fff;">${escapeHtml(o.customer_name)}</strong> (${escapeHtml(o.customer_email)})<br>
        Shipping Address: <strong style="color: #fff;">${escapeHtml(o.shipping_address)}</strong><br>
        Status: <span class="badge badge-${o.status.toLowerCase()}">${o.status}</span>
      </div>
      <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted);">Line Items</div>
      <div>${itemsHtml}</div>
      <div style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.85rem; padding-top: 0.5rem;">
        <div style="display: flex; justify-content: space-between;"><span>Subtotal:</span><span>$${o.subtotal.toFixed(2)}</span></div>
        ${o.discount_amount > 0 ? `<div style="display: flex; justify-content: space-between; color: var(--emerald);"><span>Discount (${o.coupon_code}):</span><span>-$${o.discount_amount.toFixed(2)}</span></div>` : ''}
        <div style="display: flex; justify-content: space-between;"><span>Freight:</span><span>$${o.shipping_cost.toFixed(2)}</span></div>
        <div style="display: flex; justify-content: space-between;"><span>Sales Tax:</span><span>$${o.sales_tax.toFixed(2)}</span></div>
        <div style="display: flex; justify-content: space-between; font-size: 1.1rem; font-weight: 700; border-top: 1px solid var(--border-subtle); padding-top: 0.5rem; color: var(--gold);">
          <span>Grand Total:</span><span>$${o.grand_total.toFixed(2)} USD</span>
        </div>
      </div>
    `;

    invoiceModal.classList.add('open');
  } catch (err) {
    console.error(err);
  }
};

function closeInvoice() {
  invoiceModal.classList.remove('open');
}
closeInvoiceBtn.addEventListener('click', closeInvoice);
closeInvoiceModalBtn.addEventListener('click', closeInvoice);

// Merchant KPIs
async function loadMerchantKPIs() {
  try {
    const res = await fetch(`${API_BASE}/api/analytics/store-metrics`);
    const data = await res.json();

    kpiGrossRev.textContent = `$${data.total_revenue.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    kpiOrderCount.textContent = data.completed_orders;
    kpiLowStock.textContent = data.low_stock_skus_count;
  } catch (err) {
    console.warn('KPI fetch skipped');
  }
}

refreshOrdersBtn.addEventListener('click', () => {
  loadMerchantOrders();
  loadMerchantKPIs();
});

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// Initialization
loadProducts();
