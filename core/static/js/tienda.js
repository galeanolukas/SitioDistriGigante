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

    // ---------- Previsualización rápida de producto ----------
    var qvModal = null;
    var qvProductId = null;
    var qvQty = 1;

    function fmt(n) { return '$' + Math.round(n).toLocaleString('es-AR'); }

    function openQuickView(productId) {
        fetch('/tienda/api/producto/' + productId + '/')
            .then(function (r) { return r.json(); })
            .then(function (p) {
                qvProductId = p.id;
                qvQty = 1;
                document.getElementById('qvCantidad').textContent = qvQty;
                document.getElementById('qvImg').src = p.imagen;
                document.getElementById('qvImg').alt = p.nombre;
                document.getElementById('qvMarca').textContent = p.marca;
                document.getElementById('qvNombre').textContent = p.nombre;
                document.getElementById('qvPack').textContent =
                    p.pack ? 'x' + p.pack + ' unidades' : '';
                document.getElementById('qvDescripcion').innerHTML = p.descripcion;
                document.getElementById('qvDetalle').href = p.detalle_url;

                var badge = document.getElementById('qvBadge');
                var tachado = document.getElementById('qvPrecioTachado');
                if (p.oferta) {
                    badge.textContent = p.oferta.badge;
                    badge.hidden = false;
                    tachado.textContent = fmt(p.oferta.precio_anterior);
                    tachado.hidden = false;
                } else {
                    badge.hidden = true;
                    tachado.hidden = true;
                }
                var qvPrecio = document.getElementById('qvPrecio');
                qvPrecio.textContent = fmt(p.precio);
                qvPrecio.className = 'precio-final' + (p.oferta ? ' oferta' : '');

                qvModal = qvModal || new bootstrap.Modal('#quickView');
                qvModal.show();
            });
    }

    document.addEventListener('click', function (e) {
        var qv = e.target.closest('[data-quick-view]');
        if (qv) {
            e.preventDefault();
            openQuickView(qv.dataset.productId);
            return;
        }
        if (e.target.id === 'qvMas' || e.target.id === 'qvMenos') {
            qvQty = Math.max(1, qvQty + (e.target.id === 'qvMas' ? 1 : -1));
            document.getElementById('qvCantidad').textContent = qvQty;
            return;
        }
        if (e.target.closest('#qvAgregar')) {
            postCart({ action: 'add', product_id: qvProductId, cantidad: qvQty })
                .then(function (data) {
                    if (data.ok) {
                        updateBadges(data.count);
                        toast('Producto agregado al pedido');
                        if (qvModal) qvModal.hide();
                    }
                });
            return;
        }

        // Detalle de producto: stepper + agregar + copiar link
        if (e.target.id === 'detMas' || e.target.id === 'detMenos') {
            var detSpan = document.getElementById('detCantidad');
            var detQty = Math.max(1, parseInt(detSpan.textContent, 10) +
                                  (e.target.id === 'detMas' ? 1 : -1));
            detSpan.textContent = detQty;
            return;
        }
        var detBtn = e.target.closest('#detAgregar');
        if (detBtn) {
            var cant = parseInt(document.getElementById('detCantidad').textContent, 10);
            postCart({ action: 'add', product_id: detBtn.dataset.productId, cantidad: cant })
                .then(function (data) {
                    if (data.ok) {
                        updateBadges(data.count);
                        toast('Producto agregado al pedido');
                    }
                });
            return;
        }
        var copyBtn = e.target.closest('#copiarLink');
        if (copyBtn) {
            var url = copyBtn.dataset.url;
            (navigator.clipboard
                ? navigator.clipboard.writeText(url)
                : Promise.reject()).then(function () {
                    copyBtn.innerHTML = '<i class="bi bi-check2"></i> Copiado';
                }).catch(function () {
                    window.prompt('Copiá el link:', url);
                });
            return;
        }

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
