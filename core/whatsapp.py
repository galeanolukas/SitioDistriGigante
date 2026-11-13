from urllib.parse import quote


def limpiar_numero(numero):
    """Deja solo dígitos; wa.me requiere formato internacional sin +.
    Si es un celular argentino de 10 dígitos (sin código país), agrega '549'."""
    num = ''.join(c for c in (numero or '') if c.isdigit())
    if len(num) == 10 and not num.startswith('54'):
        num = '549' + num
    return num


def wa_url(numero, texto=''):
    """Genera un link https://wa.me/<num>?text=<texto>"""
    num = limpiar_numero(numero)
    return f"https://wa.me/{num}?text={quote(texto)}"


def mensaje_pedido(pedido):
    """Texto del pedido para enviar al negocio por WhatsApp"""
    lineas = [
        f"*Nuevo pedido #{pedido.id}*",
        f"Cliente: {pedido.contacto_nombre}",
        "",
        "*Productos:*",
    ]
    for det in pedido.detalles_pedido.select_related('producto'):
        lineas.append(f"• {det.cantidad}x {det.producto.nombre} — ${det.subtotal:,.0f}".replace(',', '.'))
    if pedido.costo_envio:
        lineas.append(f"• Envío — ${pedido.costo_envio:,.0f}".replace(',', '.'))
    lineas += [
        "",
        f"*Total: ${(pedido.total_precio + (pedido.costo_envio or 0)):,.0f}*".replace(',', '.'),
    ]
    if pedido.opcion_envio:
        lineas.append(f"Envío: {pedido.opcion_envio.nombre}")
    if pedido.cliente and pedido.cliente.direccion:
        dir_txt = pedido.cliente.direccion
        if pedido.cliente.localidad:
            dir_txt += f", {pedido.cliente.localidad}"
        lineas.append(f"Dirección: {dir_txt}")
    if pedido.observaciones:
        lineas.append(f"Obs: {pedido.observaciones}")
    return "\n".join(lineas)


def mensaje_estado(pedido):
    """Texto para notificar al cliente el estado de su pedido"""
    estado = pedido.get_estado_display()
    return (f"Hola {pedido.contacto_nombre}, te escribimos de Distribuidora Gigante. "
            f"Tu pedido #{pedido.id} está en estado: *{estado}*. "
            f"Total: ${(pedido.total_precio + (pedido.costo_envio or 0)):,.0f}.".replace(',', '.'))
