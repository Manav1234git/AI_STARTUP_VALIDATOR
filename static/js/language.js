const translations = {
    en: {
        platform: "Platform",
        methodology: "Methodology",
        why_us: "Why Us",
        pricing: "Pricing",
        sign_in: "Sign In",
        validate_btn: "Validate Idea",
        hero_title: "Stop Guessing. Start Building with Certainty.",
        hero_subtitle: "Not a generic chatbot. We are your virtual co-founder.",
        input_placeholder: "Describe your startup idea in a few sentences...",
        run_btn: "Run Diagnostics",
        startup_type: "Startup Type",
        validate_btn2: "Validate Idea"
    },

    hi: {
        platform: "प्लेटफ़ॉर्म",
        methodology: "कार्यप्रणाली",
        why_us: "क्यों हम",
        pricing: "मूल्य निर्धारण",
        sign_in: "साइन इन",
        validate_btn: "आइडिया जांचें",
        hero_title: "अनुमान बंद करें। निश्चितता के साथ निर्माण शुरू करें।",
        hero_subtitle: "यह सिर्फ चैटबॉट नहीं है, यह आपका वर्चुअल को-फाउंडर है।",
        input_placeholder: "अपने स्टार्टअप आइडिया का वर्णन करें...",
        run_btn: "डायग्नोस्टिक्स चलाएं",
        startup_type: "स्टार्टअप प्रकार",
        validate_btn2: "आइडिया जांचें"
    },

    es: {
        platform: "Plataforma",
        methodology: "Metodología",
        why_us: "Por qué nosotros",
        pricing: "Precios",
        sign_in: "Iniciar sesión",
        validate_btn: "Validar idea",
        hero_title: "Deja de adivinar. Empieza a construir con certeza.",
        hero_subtitle: "No es un chatbot genérico. Somos tu cofundador virtual.",
        input_placeholder: "Describe tu idea de startup en pocas palabras...",
        run_btn: "Ejecutar diagnóstico",
        startup_type: "Tipo de Startup",
        validate_btn2: "Validar idea"
    },

    fr: {
        platform: "Plateforme",
        methodology: "Méthodologie",
        why_us: "Pourquoi nous",
        pricing: "Tarification",
        sign_in: "Se connecter",
        validate_btn: "Valider l'idée",
        hero_title: "Arrêtez de deviner. Commencez à construire avec certitude.",
        hero_subtitle: "Pas un chatbot classique. Nous sommes votre cofondateur virtuel.",
        input_placeholder: "Décrivez votre idée de startup en quelques phrases...",
        run_btn: "Lancer le diagnostic",
        startup_type: "Type de startup",
        validate_btn2: "Valider l'idée"
    }
};


// 🔁 FULL FIXED FUNCTION
function changeLanguage(lang) {
    const elements = document.querySelectorAll("[data-key]");

    elements.forEach(el => {
        const key = el.getAttribute("data-key");

        if (translations[lang] && translations[lang][key]) {

            // INPUT / TEXTAREA
            if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
                el.placeholder = translations[lang][key];
            }

            // SELECT (first option)
            else if (el.tagName === "SELECT") {
                if (el.options.length > 0) {
                    el.options[0].text = translations[lang][key];
                }
            }

            // NORMAL TEXT
            else {
                el.innerText = translations[lang][key];
            }
        }
    });

    localStorage.setItem("language", lang);

    // Update navbar label
    const label = document.getElementById("current-lang");
    if (label) label.innerText = lang.toUpperCase();
}


// 🔄 Load saved language
window.onload = () => {
    const savedLang = localStorage.getItem("language") || "en";
    changeLanguage(savedLang);
};