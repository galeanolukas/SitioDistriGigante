function openLoginModal() {
    document.getElementById('registerModal').style.display = 'none';
    document.getElementById('loginModal').style.display = 'block';
}

// Función de depuración para verificar el modal
function debugRegisterModal() {
    console.log('=== DEBUG MODAL REGISTRO ===');
    
    // Verificar si el modal existe
    const modal = document.getElementById('registerModal');
    console.log('Modal registerModal encontrado:', !!modal);
    
    if (modal) {
        console.log('Estilo actual del modal:', modal.style.display);
        console.log('Clases del modal:', modal.className);
    }
    
    // Verificar si la función openRegisterModal existe
    console.log('Función openRegisterModal existe:', typeof openRegisterModal === 'function');
    
    // Verificar si el loginModal existe
    const loginModal = document.getElementById('loginModal');
    console.log('Modal loginModal encontrado:', !!loginModal);
    
    // Intentar abrir el modal manualmente
    try {
        if (modal) {
            modal.style.display = 'block';
            console.log('Intento de abrir modal ejecutado');
        }
    } catch (error) {
        console.error('Error al intentar abrir el modal:', error);
    }
}

// Hacer la función de depuración global
window.debugRegisterModal = debugRegisterModal;

function openRegisterModal() {
    // Cerrar login modal si está abierto
    const loginModal = document.getElementById('loginModal');
    if (loginModal) {
        loginModal.style.display = 'none';
    }
    
    // Abrir register modal - igual que el DOM directo
    const registerModal = document.getElementById('registerModal');
    if (registerModal) {
        registerModal.style.display = 'block';
        
        // Renderizar CAPTCHA en el modal
        renderModalCaptcha();
    }
}

// Función para renderizar CAPTCHA en el modal
function renderModalCaptcha() {
    const container = document.getElementById('modalCaptchaContainer');
    if (container && typeof grecaptcha !== 'undefined') {
        // Limpiar el contenedor primero
        container.innerHTML = '';
        
        // Renderizar el widget de reCAPTCHA
        grecaptcha.render(container, {
            'sitekey': '6Ldwm-YsAAAAAKtyV9bL7frQb1NKdvSI549UB0iG', // Clave real de producción
            'callback': function(response) {
                // Ocultar mensaje de error cuando el CAPTCHA se resuelve
                document.getElementById('modalCaptchaError').style.display = 'none';
            },
            'expired-callback': function() {
                // Mostrar mensaje de error cuando el CAPTCHA expira
                document.getElementById('modalCaptchaError').style.display = 'block';
            }
        });
    }
}

// Función de prueba forzada
function forceOpenRegisterModal() {
    console.log('=== FUERZA ABRIR MODAL REGISTRO ===');
    const modal = document.getElementById('registerModal');
    if (modal) {
        modal.style.display = 'block';
        modal.style.visibility = 'visible';
        modal.style.opacity = '1';
        modal.style.zIndex = '9999';
        console.log('Modal forzado a abrirse');
    } else {
        console.error('Modal no encontrado');
    }
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.nextElementSibling.querySelector('i');

    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    }
}

window.onclick = function(event) {
    const loginModal = document.getElementById('loginModal');
    const registerModal = document.getElementById('registerModal');

    if (event.target === loginModal) {
        loginModal.style.display = 'none';
    }
    if (event.target === registerModal) {
        registerModal.style.display = 'none';
    }
}

// Validación y envío del formulario de registro con AJAX
document.getElementById('registerFormModal').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const password = document.getElementById('regPassword');
    const confirmPassword = document.getElementById('regConfirmPassword');
    const passwordPattern = /^(?=.*[A-Z])(?=.*[!@#$%^&*]).{8,}$/;
    const submitBtn = this.querySelector('button[type="submit"]');
    
    // Limpiar mensajes de error anteriores
    clearErrors();
    
    // Validaciones
    if (!passwordPattern.test(password.value)) {
        showError('regPassword', 'La contraseña debe tener al menos 8 caracteres, una mayúscula y un símbolo.');
        return false;
    }

    if (password.value !== confirmPassword.value) {
        showError('regConfirmPassword', 'Las contraseñas no coinciden.');
        return false;
    }

    // Validar CAPTCHA
    const captchaResponse = grecaptcha.getResponse();
    if (!captchaResponse) {
        document.getElementById('modalCaptchaError').style.display = 'block';
        return false;
    } else {
        document.getElementById('modalCaptchaError').style.display = 'none';
    }
    
    // Deshabilitar botón y mostrar loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Registrando...';
    
    // Enviar formulario con AJAX
    const formData = new FormData(this);
    
    fetch(this.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': formData.get('csrfmiddlewaretoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Mostrar mensaje de éxito
            showNotification(data.message, 'success');
            
            // Cerrar modal
            document.getElementById('registerModal').style.display = 'none';
            
            // Redirigir si es necesario
            if (data.redirect) {
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 2000);
            }
        } else {
            // Mostrar errores
            if (data.errors) {
                Object.keys(data.errors).forEach(field => {
                    showError(field, data.errors[field]);
                });
            } else if (data.message) {
                showNotification(data.message, 'error');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error de conexión. Inténtalo nuevamente.', 'error');
    })
    .finally(() => {
        // Restaurar botón
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-user-plus"></i> REGISTRARME';
    });
});

// Función para mostrar errores de campo
function showError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (field) {
        // Remover error anterior
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
        
        // Agregar borde rojo
        field.classList.add('w3-border-red');
        
        // Crear mensaje de error
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error w3-text-red w3-small';
        errorDiv.style.marginTop = '5px';
        errorDiv.textContent = message;
        
        field.parentNode.appendChild(errorDiv);
    }
}

// Función para limpiar errores
function clearErrors() {
    document.querySelectorAll('.field-error').forEach(error => error.remove());
    document.querySelectorAll('.w3-border-red').forEach(field => {
        field.classList.remove('w3-border-red');
    });
}

// Función para mostrar notificaciones
function showNotification(message, type) {
    const notification = document.createElement('div');
    const iconClass = type === 'success' ? 'fa-check-circle' :
                     type === 'error' ? 'fa-exclamation-circle' :
                     type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle';

    const bgColor = type === 'success' ? 'w3-green' :
                   type === 'error' ? 'w3-red' :
                   type === 'warning' ? 'w3-orange' : 'w3-blue';

    notification.className = `w3-panel w3-round ${bgColor} w3-text-white w3-display-topright w3-card-4`;
    notification.style.cssText = 'position:fixed; top:100px; right:20px; z-index:10000; max-width:400px;';
    notification.innerHTML = `
        <span onclick="this.parentElement.style.display='none'" class="w3-button w3-display-topright">&times;</span>
        <h4><i class="fas ${iconClass}"></i> ${type === 'success' ? 'Éxito' : type === 'error' ? 'Error' : 'Información'}</h4>
        <p>${message}</p>
    `;

    document.body.appendChild(notification);

    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        if (notification.parentElement) {
            notification.parentElement.removeChild(notification);
        }
    }, 5000);
}

// Función para mostrar automáticamente el modal de mensajes (REMOVER - está en base.html)
// document.addEventListener('DOMContentLoaded', function() {
//     {% if messages %}
//     // Mostrar el modal de mensajes si hay mensajes
//     document.getElementById('djangoMessagesModal').style.display = 'block';
//
//     // Configurar auto-cierre después de 7 segundos
//     setTimeout(function() {
//         document.getElementById('djangoMessagesModal').style.display = 'none';
//     }, 7000);
//     {% endif %}
// });

// También agregar esta función para manejar mensajes específicos en otros modales (REMOVER - duplicado)
// function handleDjangoMessages() {
//     {% if messages %}
//     {% for message in messages %}
//         {% if 'login' in message.tags or 'register' in message.tags %}
//         // Mostrar mensajes de login/register en sus modales respectivos
//         {% if 'login' in message.tags %}
//         openLoginModal();
//         {% elif 'register' in message.tags %}
//         openRegisterModal();
//         {% endif %}
//
//         // Mostrar notificación específica
//         showNotification('{{ message|safe }}', '{{ message.tags }}');
//         {% endif %}
//     {% endfor %}
//     {% endif %}
// }

// Función mejorada para mostrar notificaciones toast
function showNotification(message, type) {
    const notification = document.createElement('div');
    const iconClass = type === 'success' ? 'fa-check-circle' :
                     type === 'error' ? 'fa-exclamation-circle' :
                     type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle';

    const bgColor = type === 'success' ? 'w3-green' :
                   type === 'error' ? 'w3-red' :
                   type === 'warning' ? 'w3-orange' : 'w3-blue';

    notification.className = `w3-panel w3-round ${bgColor} w3-text-white w3-display-topright w3-card-4`;
    notification.style.cssText = 'position:fixed; top:100px; right:20px; z-index:10000; max-width:400px;';
    notification.innerHTML = `
        <span onclick="this.parentElement.style.display='none'" class="w3-button w3-display-topright">&times;</span>
        <h4><i class="fas ${iconClass}"></i> ${type === 'success' ? 'Éxito' : type === 'error' ? 'Error' : 'Información'}</h4>
        <p>${message}</p>
    `;

    document.body.appendChild(notification);

    // Auto-eliminar después de 5 segundos
    setTimeout(function() {
        if (notification.parentElement) {
            notification.parentElement.removeChild(notification);
        }
    }, 5000);
}

// Cerrar el modal si se hace clic fuera de él
window.onclick = function(event) {
    const modal = document.getElementById('resetPassModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

// Validación del formulario
document.getElementById('formulario').addEventListener('submit', function(event) {
    const emailInput = document.querySelector('input[name="email"]');
    const emailError = document.getElementById('emailError');
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(emailInput.value)) {
        event.preventDefault();
        emailError.style.display = 'block';
        emailInput.classList.add('w3-border-red');
    } else {
        emailError.style.display = 'none';
        emailInput.classList.remove('w3-border-red');
    }
});

// Validación en tiempo real
document.querySelector('input[name="email"]').addEventListener('input', function() {
    const emailError = document.getElementById('emailError');
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (emailRegex.test(this.value)) {
        emailError.style.display = 'none';
        this.classList.remove('w3-border-red');
        this.classList.add('w3-border-green');
    } else {
        this.classList.remove('w3-border-green');
    }
});

// Función para setear el vendedor seleccionado
function setVendedor() {
    const vendedorSelect = document.getElementById('vendedorSelect');
    const vendedorHidden = document.getElementById('vendedorHidden');
    if (vendedorSelect && vendedorHidden) {
        vendedorHidden.value = vendedorSelect.value;
    }
}

// Configurar el formulario para que setee el vendedor antes de enviar
document.getElementById('pedidoForm').addEventListener('submit', function() {
    setVendedor();
});

// Función para mostrar notificaciones
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = 'w3-panel w3-round ' +
                            (type === 'error' ? 'w3-red' : 'w3-green') +
                            ' w3-display-topmiddle w3-card-4';
    notification.style.cssText = 'position:fixed; top:80px; z-index:10000; max-width:500px; width:80%;';
    notification.innerHTML = '<span onclick="this.parentElement.style.display=\'none\'" ' +
                            'class="w3-button w3-display-topright">&times;</span>' +
                            '<h4><i class="fas fa-exclamation-circle"></i> ' +
                            (type === 'error' ? 'Error' : 'Éxito') + '</h4>' +
                            '<p>' + message + '</p>';

    document.body.appendChild(notification);

    // Auto-eliminar después de 5 segundos
    setTimeout(function() {
        if (notification.parentElement) {
            notification.parentElement.removeChild(notification);
        }
    }, 5000);
}

// Cerrar modal al hacer clic fuera (solo para pedidoModal)
window.onclick = function(event) {
    // No hacer nada si se hace clic en un botón
    if (event.target.tagName === 'BUTTON' || event.target.closest('button')) {
        return;
    }
    
    const modal = document.getElementById('pedidoModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

// Abrir modal si hay parámetro en la URL
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('showModal') === 'true') {
        document.getElementById('pedidoModal').style.display = 'block';
    }
});

// Función para mostrar automáticamente el modal de mensajes (REMOVER - está en base.html)
// document.addEventListener('DOMContentLoaded', function() {
//     {% if messages %}
//     // Mostrar el modal de mensajes si hay mensajes
//     document.getElementById('djangoMessagesModal').style.display = 'block';
//
//     // Configurar auto-cierre después de 7 segundos
//     setTimeout(function() {
//         document.getElementById('djangoMessagesModal').style.display = 'none';
//     }, 7000);
//     {% endif %}
// });

function closeModal(modalId) {
  document.getElementById(modalId).close();
}

// Botón de prueba para depuración - agregar al final del body
document.addEventListener('DOMContentLoaded', function() {
    // Crear botón de prueba
    const testBtn = document.createElement('button');
    testBtn.textContent = 'PROBAR MODAL REGISTRO';
    testBtn.style.cssText = 'position:fixed;top:10px;right:10px;z-index:9999;background:red;color:white;padding:10px;';
    testBtn.onclick = function() {
        console.log('Botón de prueba presionado');
        debugRegisterModal();
        openRegisterModal();
    };
    document.body.appendChild(testBtn);
    
    // Crear botón de fuerza
    const forceBtn = document.createElement('button');
    forceBtn.textContent = 'FORZAR MODAL';
    forceBtn.style.cssText = 'position:fixed;top:60px;right:10px;z-index:9999;background:orange;color:white;padding:10px;';
    forceBtn.onclick = function() {
        console.log('Botón de fuerza presionado');
        forceOpenRegisterModal();
    };
    document.body.appendChild(forceBtn);
});

// Hacer funciones globales explícitamente
window.openLoginModal = openLoginModal;
window.openRegisterModal = openRegisterModal;
window.closeModal = closeModal;
window.togglePassword = togglePassword;
window.debugRegisterModal = debugRegisterModal;
window.forceOpenRegisterModal = forceOpenRegisterModal;
