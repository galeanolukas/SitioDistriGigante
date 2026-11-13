(function () {
    'use strict';

    function getCsrf() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function postCart(body) {
        return fetch('/tienda/api/carrito/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
            },
            body: JSON.stringify(body),
        }).then(function (r) { return r.json(); });
    }

    function updateBadges(count) {
        document.querySelectorAll('[data-cart-count]').forEach(function (el) {
            el.textContent = count;
            el.hidden = count <= 0;
        });
        document.querySelectorAll('[data-cart-count-inline]').forEach(function (el) {
            el.textContent = count;
        });
    }

    function updateTotals(data) {
        document.querySelectorAll('[data-cart-total]').forEach(function (el) {
            el.textContent = '$' + Math.round(data.total).toLocaleString('es-AR');
        });
    }

    function toast(msg) {
        var el = document.getElementById('cartToast');
        if (!el) return;
        el.querySelector('.toast-body').textContent = msg;
        bootstrap.Toast.getOrCreateInstance(el, { delay: 2500 }).show();
    }

    // Agregar al carrito desde las tarjetas
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-add-cart]');
        if (btn) {
            e.preventDefault();
            postCart({ action: 'add', product_id: btn.dataset.productId, cantidad: 1 })
                .then(function (data) {
                    if (data.ok) {
                        updateBadges(data.count);
                        toast('Producto agregado al pedido');
                        btn.classList.add('added');
                        setTimeout(function () { btn.classList.remove('added'); }, 1200);
                    }
                });
            return;
        }

        // Steppers de cantidad en la página de carrito
        var qty = e.target.closest('[data-qty]');
        if (qty) {
            var item = qty.closest('[data-cart-item]');
            var span = item.querySelector('[data-item-qty]');
            var nueva = parseInt(span.textContent, 10) + parseInt(qty.dataset.qty, 10);
            postCart({ action: 'set', product_id: qty.dataset.productId, cantidad: nueva })
                .then(function (data) {
                    if (!data.ok) return;
                    updateBadges(data.count);
                    updateTotals(data);
                    if (data.item_cantidad <= 0) {
                        item.remove();
                    } else {
                        span.textContent = data.item_cantidad;
                        item.querySelector('[data-item-subtotal]').textContent =
                            '$' + Math.round(data.item_subtotal).toLocaleString('es-AR');
                    }
                });
            return;
        }

        // Eliminar ítem
        var rm = e.target.closest('[data-remove-item]');
        if (rm) {
            var row = rm.closest('[data-cart-item]');
            postCart({ action: 'set', product_id: rm.dataset.productId, cantidad: 0 })
                .then(function (data) {
                    if (data.ok) {
                        row.remove();
                        updateBadges(data.count);
                        updateTotals(data);
                        if (data.count === 0) location.reload();
                    }
                });
        }
    });
})();
