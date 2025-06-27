document.addEventListener("DOMContentLoaded", () => {
    const chatbotToggle = document.getElementById("chatbot-toggle");
    const chatbotContainer = document.getElementById("chatbot-container");
    const chatbotClose = document.getElementById("chatbot-close");
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const chatBody = document.querySelector(".chat-body");
    const buttons = document.querySelectorAll(".quick-reply");

    let chatbotData = {}; // Store JSON data

    const API_KEY = "AIzaSyCNbs1_oec9Vdp2eMxL1pCZ8cv9bkjLlMs";
    const API_URL = `https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=${API_KEY}`;
    const chatHistory = [];

    // Load chatbot data from JSON
    fetch("data.json")
        .then(response => response.json())
        .then(data => chatbotData = data)
        .catch(error => console.error("Error loading chatbot data:", error));

    // Toggle Chatbot
    chatbotToggle.addEventListener("click", () => {
        chatbotContainer.style.display = "flex";
    });

    chatbotClose.addEventListener("click", () => {
        chatbotContainer.style.display = "none";
    });

    // Send Message
    sendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            sendMessage();
        }
    });

    // Add event listeners to buttons
    buttons.forEach(button => {
        button.addEventListener("click", async (event) => {
            let buttonText = event.target.innerText;
            appendMessage("user", buttonText);

            setTimeout(async () => {
                let botResponse = await getBotResponse(buttonText);
                appendMessage("bot", botResponse);
            }, 1000);
        });
    });

    async function sendMessage() {
        let userMessage = chatInput.value.trim();
        if (userMessage === "") return;

        appendMessage("user", userMessage);
        chatInput.value = "";

        let botResponse = await getBotResponse(userMessage);
        appendMessage("bot", botResponse);
    }

    function appendMessage(sender, text) {
        const message = document.createElement("div");
        message.classList.add("message", sender === "user" ? "user-message" : "bot-message");
        message.textContent = text;
        chatBody.appendChild(message);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    async function getBotResponse(input) {
        input = input.toLowerCase();

        // Use Google Gemini API for responses
        const geminiResponse = await fetchGeminiResponse(input);
        if (geminiResponse) return geminiResponse;

        // Check FAQ data
        for (let question in chatbotData.faq) {
            if (input.includes(question.toLowerCase())) {
                return chatbotData.faq[question];
            }
        }

        // Check Medical Info
        for (let symptom in chatbotData.medical_info) {
            if (input.includes(symptom)) {
                return chatbotData.medical_info[symptom];
            }
        }

        return "I'm sorry, I don't have an answer for that.";
    }

    async function fetchGeminiResponse(userMessage) {
        try {
            console.log("Sending request to Gemini API:", userMessage);

            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    contents: [{ parts: [{ text: userMessage }] }]
                })
            });

            if (!response.ok) {
                console.error(`Gemini API Error: ${response.status} - ${response.statusText}`);
                return "I'm having trouble responding right now. Please try again later.";
            }

            const data = await response.json();
            console.log("Received response from Gemini API:", data);

            return data.candidates?.[0]?.content?.parts?.[0]?.text || "I'm not sure how to respond to that.";
        } catch (error) {
            console.error("Error fetching Gemini response:", error);
            return "I'm having trouble connecting to the AI service.";
        }
    }
});
