// app/static/js/main.js
// JavaScript global para el Sistema de Control de Sucursales

/**
 * Objeto principal de la aplicación
 */
const SucursalesApp = {
    // Configuración
    config: {
        alertAutoDismissTime: 5000,
        loadingTimeout: 10000,
        toastDuration: 4000
    },

    // Estado de la aplicación
    state: {
        isFormSubmitting: false,
        activeToasts: []
    },

    // Inicialización principal
    init: function() {
        console.log('🚀 Iniciando Sistema de Control de Sucursales');
        
        this.setupPasswordToggles();
        this.setupPasswordStrengthIndicator();
        this.setupFormSubmissionStates();
        this.setupAlertAutoDismiss();
        this.setupBootstrapComponents();
        this.setupNavigationHighlighting();
        this.setupSmoothScrolling();
        this.setupTermsValidation();
        this.setupPasswordConfirmation();
        this.setupFormValidation();
        this.setupKeyboardShortcuts();
        
        console.log('✅ Aplicación inicializada correctamente');
    }
};

/**
 * Ejecutar cuando el DOM esté listo
 */
document.addEventListener('DOMContentLoaded', function() {
    SucursalesApp.init();
});

/**
 * 1. Toggle de visibilidad de contraseña
 */
SucursalesApp.setupPasswordToggles = function() {
    function setupPasswordToggle(toggleButtonId, passwordFieldId, iconId) {
        const toggle = document.getElementById(toggleButtonId);
        const field = document.getElementById(passwordFieldId);
        const icon = document.getElementById(iconId);
        
        if (!toggle || !field || !icon) return;
        
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            
            const isPassword = field.getAttribute('type') === 'password';
            const newType = isPassword ? 'text' : 'password';
            
            field.setAttribute('type', newType);
            
            // Actualizar icono
            if (isPassword) {
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
                toggle.setAttribute('aria-label', 'Ocultar contraseña');
            } else {
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
                toggle.setAttribute('aria-label', 'Mostrar contraseña');
            }
            
            // Mantener el foco en el campo de contraseña
            field.focus();
        });
        
        // Configurar atributos de accesibilidad
        toggle.setAttribute('aria-label', 'Mostrar contraseña');
        toggle.setAttribute('tabindex', '0');
    }
    
    // Aplicar a todos los campos de contraseña comunes
    setupPasswordToggle('togglePassword', 'passwordField', 'togglePasswordIcon');
    setupPasswordToggle('togglePassword2', 'password2Field', 'togglePassword2Icon');
    setupPasswordToggle('toggleCurrentPassword', 'currentPasswordField', 'toggleCurrentPasswordIcon');
    setupPasswordToggle('toggleNewPassword', 'newPasswordField', 'toggleNewPasswordIcon');
};

/**
 * 2. Indicador de fortaleza de contraseña
 */
SucursalesApp.setupPasswordStrengthIndicator = function() {
    const passwordField = document.getElementById('passwordField');
    const strengthBar = document.getElementById('passwordStrength');
    const strengthText = document.getElementById('passwordStrengthText');
    
    if (!passwordField || !strengthBar || !strengthText) return;
    
    passwordField.addEventListener('input', function() {
        const password = this.value;
        const result = calculatePasswordStrength(password);
        
        updateStrengthIndicator(strengthBar, strengthText, result);
    });
    
    function calculatePasswordStrength(password) {
        let strength = 0;
        let feedback = [];
        
        // Criterios de fortaleza
        const criteria = {
            length: password.length >= 8,
            lowercase: /[a-z]/.test(password),
            uppercase: /[A-Z]/.test(password),
            numbers: /[0-9]/.test(password),
            special: /[^a-zA-Z0-9]/.test(password)
        };
        
        // Calcular puntuación
        if (criteria.length) strength += 20;
        if (criteria.lowercase) strength += 20;
        if (criteria.uppercase) strength += 20;
        if (criteria.numbers) strength += 20;
        if (criteria.special) strength += 20;
        
        // Bonificaciones
        if (password.length >= 12) strength += 10;
        if (password.length >= 16) strength += 10;
        
        // Penalizaciones por patrones comunes
        if (/(.)\1{2,}/.test(password)) strength -= 20; // Caracteres repetidos
        if (/123|abc|qwe|asd/i.test(password)) strength -= 15; // Secuencias comunes
        
        // Asegurar rango 0-100
        strength = Math.max(0, Math.min(100, strength));
        
        // Determinar nivel y color
        let level, className, text;
        if (strength === 0) {
            level = 0;
            className = '';
            text = '-';
        } else if (strength <= 30) {
            level = strength;
            className = 'weak';
            text = 'Muy débil';
        } else if (strength <= 50) {
            level = strength;
            className = 'fair';
            text = 'Débil';
        } else if (strength <= 75) {
            level = strength;
            className = 'good';
            text = 'Buena';
        } else {
            level = strength;
            className = 'strong';
            text = 'Fuerte';
        }
        
        return { level, className, text, criteria };
    }
    
    function updateStrengthIndicator(bar, textElement, result) {
        bar.style.width = result.level + '%';
        bar.className = 'progress-bar ' + result.className;
        textElement.textContent = result.text;
        
        // Agregar clase CSS al contenedor para feedback visual adicional
        const container = bar.closest('.password-strength-container');
        if (container) {
            container.className = 'password-strength-container ' + result.className;
        }
    }
};

/**
 * 3. Estado de carga del botón de envío
 */
SucursalesApp.setupFormSubmissionStates = function() {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (SucursalesApp.state.isFormSubmitting) {
                e.preventDefault();
                return false;
            }
            
            const submitButton = form.querySelector('.btn[type="submit"]');
            if (!submitButton) return;
            
            // Validar formulario antes de mostrar loading
            if (!form.checkValidity()) {
                return;
            }
            
            SucursalesApp.state.isFormSubmitting = true;
            
            // Guardar estado original
            const originalText = submitButton.innerHTML;
            const originalDisabled = submitButton.disabled;
            
            // Aplicar estado de carga
            submitButton.classList.add('btn-loading');
            submitButton.disabled = true;
            submitButton.setAttribute('aria-busy', 'true');
            
            // Timeout de seguridad
            const timeout = setTimeout(() => {
                restoreButton();
                showToast('La operación está tardando más de lo esperado. Por favor, intenta de nuevo.', 'warning');
            }, SucursalesApp.config.loadingTimeout);
            
            function restoreButton() {
                submitButton.classList.remove('btn-loading');
                submitButton.disabled = originalDisabled;
                submitButton.innerHTML = originalText;
                submitButton.removeAttribute('aria-busy');
                SucursalesApp.state.isFormSubmitting = false;
                clearTimeout(timeout);
            }
            
            // Escuchar eventos de página para restaurar botón
            window.addEventListener('beforeunload', restoreButton);
            window.addEventListener('pageshow', restoreButton);
        });
    });
};

/**
 * 4. Auto-dismiss de alertas
 */
SucursalesApp.setupAlertAutoDismiss = function() {
    const alerts = document.querySelectorAll('.alert:not(.alert-important):not(.alert-persistent)');
    
    alerts.forEach(function(alert) {
        // Solo auto-dismiss alertas de éxito e info
        if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')) {
            setTimeout(function() {
                if (alert && alert.parentNode && !alert.classList.contains('fade')) {
                    const bsAlert = new bootstrap.Alert(alert);
                    if (bsAlert) {
                        bsAlert.close();
                    }
                }
            }, SucursalesApp.config.alertAutoDismissTime);
        }
    });
};

/**
 * 5. Inicialización de componentes de Bootstrap
 */
SucursalesApp.setupBootstrapComponents = function() {
    // Inicializar tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            delay: { show: 500, hide: 100 }
        });
    });
    
    // Inicializar popovers
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    const popoverList = [...popoverTriggerList].map(popoverTriggerEl => {
        return new bootstrap.Popover(popoverTriggerEl, {
            trigger: 'focus'
        });
    });
    
    // Configurar dropdowns para cerrar al hacer clic afuera
    document.addEventListener('click', function(e) {
        const dropdowns = document.querySelectorAll('.dropdown-menu.show');
        dropdowns.forEach(dropdown => {
            if (!dropdown.contains(e.target) && !dropdown.previousElementSibling.contains(e.target)) {
                const bsDropdown = bootstrap.Dropdown.getInstance(dropdown.previousElementSibling);
                if (bsDropdown) {
                    bsDropdown.hide();
                }
            }
        });
    });
};

/**
 * 6. Resaltado de navegación activa
 */
SucursalesApp.setupNavigationHighlighting = function() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(function(link) {
        const linkPath = new URL(link.href).pathname;
        
        // Coincidencia exacta o coincidencia de inicio de ruta
        if (linkPath === currentPath || (currentPath.startsWith(linkPath) && linkPath !== '/')) {
            link.classList.add('active');
            link.setAttribute('aria-current', 'page');
        } else {
            link.classList.remove('active');
            link.removeAttribute('aria-current');
        }
    });
};

/**
 * 7. Smooth scrolling para enlaces ancla
 */
SucursalesApp.setupSmoothScrolling = function() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            
            // Ignorar enlaces vacíos o solo #
            if (href === '#' || href === '') return;
            
            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                
                const headerOffset = 70; // Espacio para navbar fija
                const elementPosition = target.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
                
                // Enfocar elemento para accesibilidad
                setTimeout(() => {
                    target.tabIndex = -1;
                    target.focus();
                }, 500);
            }
        });
    });
};

/**
 * 8. Validación de términos y condiciones
 */
SucursalesApp.setupTermsValidation = function() {
    const termsCheck = document.getElementById('termsCheck');
    const forms = document.querySelectorAll('form');
    
    if (!termsCheck) return;
    
    forms.forEach(form => {
        if (form.contains(termsCheck)) {
            form.addEventListener('submit', function(e) {
                if (!termsCheck.checked) {
                    e.preventDefault();
                    
                    // Mostrar error visual
                    termsCheck.classList.add('is-invalid');
                    
                    // Crear o actualizar mensaje de error
                    let errorDiv = form.querySelector('.terms-error');
                    if (!errorDiv) {
                        errorDiv = document.createElement('div');
                        errorDiv.className = 'alert alert-danger terms-error mt-2';
                        errorDiv.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Debes aceptar los términos y condiciones para continuar.';
                        termsCheck.closest('.form-check').parentNode.insertBefore(errorDiv, termsCheck.closest('.form-check').nextSibling);
                    }
                    
                    // Scroll al error
                    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    
                    // Enfocar checkbox
                    termsCheck.focus();
                    
                    return false;
                }
            });
            
            // Limpiar error cuando se marque el checkbox
            termsCheck.addEventListener('change', function() {
                if (this.checked) {
                    this.classList.remove('is-invalid');
                    const errorDiv = form.querySelector('.terms-error');
                    if (errorDiv) {
                        errorDiv.remove();
                    }
                }
            });
        }
    });
};

/**
 * 9. Validación de confirmación de contraseña en tiempo real
 */
SucursalesApp.setupPasswordConfirmation = function() {
    const passwordField = document.getElementById('passwordField');
    const password2Field = document.getElementById('password2Field');
    
    if (!passwordField || !password2Field) return;
    
    function validatePasswordMatch() {
        const password = passwordField.value;
        const confirmPassword = password2Field.value;
        
        if (confirmPassword && password !== confirmPassword) {
            password2Field.classList.add('is-invalid');
            
            // Agregar mensaje de error si no existe
            let errorDiv = password2Field.parentNode.parentNode.querySelector('.password-match-error');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback password-match-error d-block';
                errorDiv.innerHTML = '<i class="fas fa-exclamation-circle me-1"></i>Las contraseñas no coinciden';
                password2Field.parentNode.parentNode.appendChild(errorDiv);
            }
        } else {
            password2Field.classList.remove('is-invalid');
            const errorDiv = password2Field.parentNode.parentNode.querySelector('.password-match-error');
            if (errorDiv) {
                errorDiv.remove();
            }
        }
    }
    
    password2Field.addEventListener('input', validatePasswordMatch);
    passwordField.addEventListener('input', validatePasswordMatch);
};

/**
 * 10. Validación general de formularios
 */
SucursalesApp.setupFormValidation = function() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        // Validación en tiempo real
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
            
            input.addEventListener('input', function() {
                if (this.classList.contains('is-invalid') && this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                }
            });
        });
    });
};

/**
 * 11. Atajos de teclado
 */
SucursalesApp.setupKeyboardShortcuts = function() {
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + / para mostrar ayuda de atajos
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            showKeyboardShortcuts();
        }
        
        // Escape para cerrar modales y dropdowns
        if (e.key === 'Escape') {
            // Cerrar modales abiertos
            const openModals = document.querySelectorAll('.modal.show');
            openModals.forEach(modal => {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) bsModal.hide();
            });
            
            // Cerrar dropdowns abiertos
            const openDropdowns = document.querySelectorAll('.dropdown-menu.show');
            openDropdowns.forEach(dropdown => {
                const bsDropdown = bootstrap.Dropdown.getInstance(dropdown.previousElementSibling);
                if (bsDropdown) bsDropdown.hide();
            });
        }
    });
    
    function showKeyboardShortcuts() {
        showToast('Atajos: Ctrl+/ (ayuda), Esc (cerrar)', 'info');
    }
};

/**
 * Función global para mostrar notificaciones toast
 */
function showToast(message, type = 'info', duration = null) {
    const types = {
        'success': { icon: 'check-circle', class: 'bg-success' },
        'error': { icon: 'exclamation-triangle', class: 'bg-danger' },
        'danger': { icon: 'exclamation-triangle', class: 'bg-danger' },
        'warning': { icon: 'exclamation-triangle', class: 'bg-warning text-dark' },
        'info': { icon: 'info-circle', class: 'bg-info' }
    };
    
    const toastType = types[type] || types.info;
    const toastDuration = duration || SucursalesApp.config.toastDuration;
    
    const toastHtml = `
        <div class="toast align-items-center text-white ${toastType.class} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${toastType.icon} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Cerrar"></button>
            </div>
        </div>
    `;
    
    // Obtener o crear contenedor de toasts
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '9999';
        document.body.appendChild(toastContainer);
    }
    
    // Agregar toast
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastElement = toastContainer.lastElementChild;
    
    // Inicializar y mostrar toast
    const toast = new bootstrap.Toast(toastElement, {
        delay: toastDuration
    });
    
    toast.show();
    
    // Agregar a estado activo
    SucursalesApp.state.activeToasts.push(toast);
    
    // Limpiar cuando se oculte
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
        const index = SucursalesApp.state.activeToasts.indexOf(toast);
        if (index > -1) {
            SucursalesApp.state.activeToasts.splice(index, 1);
        }
    });
    
    return toast;
}

/**
 * Funciones utilitarias globales
 */
window.SucursalesUtils = {
    // Formatear fecha
    formatDate: function(date, locale = 'es-AR') {
        return new Intl.DateTimeFormat(locale).format(new Date(date));
    },
    
    // Formatear moneda
    formatCurrency: function(amount, currency = 'ARS') {
        return new Intl.NumberFormat('es-AR', {
            style: 'currency',
            currency: currency
        }).format(amount);
    },
    
    // Debounce function
    debounce: function(func, wait, immediate) {
        let timeout;
        return function executedFunction() {
            const context = this;
            const args = arguments;
            const later = function() {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(context, args);
        };
    },
    
    // Throttle function
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

// Exponer funciones globales necesarias
window.showToast = showToast;
window.SucursalesApp = SucursalesApp;

// Manejar errores globales
window.addEventListener('error', function(e) {
    console.error('Error global capturado:', e.error);
    if (window.location.hostname !== 'localhost') {
        showToast('Ha ocurrido un error inesperado. Por favor, recarga la página.', 'error');
    }
});

// Manejar errores de promesas no capturadas
window.addEventListener('unhandledrejection', function(e) {
    console.error('Promesa rechazada no manejada:', e.reason);
    if (window.location.hostname !== 'localhost') {
        showToast('Error de conexión. Verifica tu conexión a internet.', 'warning');
    }
});

// Log de carga exitosa
console.log('📱 main.js cargado exitosamente');