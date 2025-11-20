// Vivants - JavaScript para o template original
const  Menu = document.querySelector(".menu_mobile")
const   nav_menu = document.querySelector('.menu')
const  icon  = Menu.querySelector('i')

Menu.addEventListener("click", ()=>{
    nav_menu.classList.toggle("active")
    if (icon.classList.contains('fa-bars')){
        icon.classList.remove('fa-bars');
        icon.classList.add("fa-times");
    }else{
        icon.classList.remove("fa-times");
        icon.classList.add("fa-bars");

    }

})


document.addEventListener('DOMContentLoaded', function() {
    // Slider Principal
    initMainSlider();

    // Slider Matéria Prima
    initMpSlider();

    // Menu Mobile
    initMobileMenu();

    // Newsletter
    initNewsletter();
});

// Slider Principal
function initMainSlider() {
    const slidesContainer = document.querySelector('.slides_container');
    const slides = document.querySelectorAll('.img_slider');

    if (!slidesContainer || slides.length === 0) return;

    let currentSlide = 0;
    const totalSlides = slides.length;

    function showSlide(index) {
        const translateX = -index * 100;
        slidesContainer.style.transform = `translateX(${translateX}%)`;
    }

    function nextSlide() {
        currentSlide = (currentSlide + 1) % totalSlides;
        showSlide(currentSlide);
    }

    // Iniciar slider
    showSlide(0);

    // Trocar slide a cada 5 segundos
    setInterval(nextSlide, 5000);
}

// Slider Matéria Prima
function initMpSlider() {
    const mpSlides = document.querySelectorAll('.img_mp');

    if (mpSlides.length === 0) return;

    let currentMpSlide = 0;
    const totalMpSlides = mpSlides.length;

    function showMpSlide(index) {
        mpSlides.forEach(slide => slide.classList.remove('active'));
        mpSlides[index].classList.add('active');
    }

    function nextMpSlide() {
        currentMpSlide = (currentMpSlide + 1) % totalMpSlides;
        showMpSlide(currentMpSlide);
    }

    // Iniciar slider matéria prima
    if (mpSlides.length > 0) {
        showMpSlide(0);
        setInterval(nextMpSlide, 4000);
    }
}

// Menu Mobile
function initMobileMenu() {
    const mobileMenu = document.querySelector('.mobile');
    const menu = document.querySelector('.menu');

    if (mobileMenu && menu) {
        mobileMenu.addEventListener('click', function() {
            menu.style.display = menu.style.display === 'flex' ? 'none' : 'flex';
        });
    }

    // Fechar menu ao clicar fora
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.menu') && !e.target.closest('.mobile')) {
            if (menu && window.innerWidth <= 768) {
                menu.style.display = 'none';
            }
        }
    });
}

// Newsletter
function initNewsletter() {
    const newsletterForm = document.querySelector('.foot_4 form');

    if (newsletterForm) {
        newsletterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const emailInput = this.querySelector('input[type="email"]');
            const email = emailInput.value;

            if (validateEmail(email)) {
                // Simular envio
                alert('Obrigado por assinar nossa newsletter! Entraremos em contato em breve.');
                emailInput.value = '';
            } else {
                alert('Por favor, insira um email válido.');
            }
        });
    }
}

// Validação de Email
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Troca de Idioma
function initLanguageSwitch() {
    const languageSelect = document.getElementById('language-select');

    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const selectedLanguage = this.value;
            // Aqui você pode implementar a lógica de troca de idioma
            console.log('Idioma selecionado:', selectedLanguage);
        });
    }
}

// Inicializar quando a página carregar
window.addEventListener('load', function() {
    initLanguageSwitch();
});

// Smooth Scroll para âncoras
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});
