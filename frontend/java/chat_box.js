// Cấu hình thư viện Markdown
if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
}

const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const typingContainer = document.getElementById('typingContainer');

let conversationHistory = [];
const WELCOME_MSG = "Dạ, em chào Anh/Chị! Em có thể hỗ trợ thông tin mẫu xe nào cho mình hôm nay ạ?";

// Tự động chỉnh độ cao ô nhập liệu
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight - 16) + 'px';
});

function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Lưu xưng hô của khách hàng (Anh / Chị)
function extractPronoun(text) {
    const lower = text.toLowerCase();
    if (/\b(anh)\b/.test(lower)) localStorage.setItem('userPronoun', 'anh');
    else if (/\b(chị)\b/.test(lower)) localStorage.setItem('userPronoun', 'chị');
}

// Format văn bản Markdown đẹp mắt
function formatMarkdown(text) {
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        return DOMPurify.sanitize(marked.parse(text));
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    extractPronoun(text);

    // 1. Thêm tin nhắn người dùng
    appendMessage(text, 'user');
    userInput.value = '';
    userInput.style.height = '24px';
    userInput.disabled = true;
    if (sendBtn) sendBtn.disabled = true;

    // 2. Hiệu ứng Bot đang suy nghĩ
    showTyping(true);

    try {
        // 3. Gọi API server backend (server.py)
        const response = await fetch('http://127.0.0.1:8000/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                history: conversationHistory
            })
        });

        const data = await response.json();

        if (response.ok) {
            showTyping(false);
            appendMessage(data.response, 'assistant');
            
            // Cập nhật lịch sử hội thoại
            conversationHistory.push({ role: 'user', content: text });
            conversationHistory.push({ role: 'assistant', content: data.response });
        } else {
            showTyping(false);
            appendMessage('Dạ, hệ thống đang bận xử lý thông số. Anh/Chị vui lòng thử lại sau giây lát ạ.', 'assistant');
        }
    } catch (error) {
        console.error('Lỗi API:', error);
        showTyping(false);
        const pronoun = localStorage.getItem('userPronoun') || 'Quý khách';
        appendMessage(`Cảm ơn ${pronoun} đã quan tâm. Kết nối server AI (port 8000) hiện bị gián đoạn. Anh/Chị vui lòng kiểm tra lại server backend ạ.`, 'assistant');
    } finally {
        userInput.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        userInput.focus();
    }
}

function appendMessage(text, sender) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    
    const avatarIcon = sender === 'user' ? 'fa-user' : 'fa-robot';
    const contentHTML = sender === 'assistant' ? formatMarkdown(text) : escapeHtml(text);

    msgDiv.innerHTML = `
        <div class="msg-avatar"><i class="fa-solid ${avatarIcon}"></i></div>
        <div>
            <div class="msg-content">${contentHTML}</div>
            <span class="msg-time">${getCurrentTime()}</span>
        </div>
    `;

    chatMessages.insertBefore(msgDiv, typingContainer);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping(show) {
    typingContainer.style.display = show ? 'flex' : 'none';
    chatMessages.appendChild(typingContainer);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
}

// Hàm khởi tạo lại cuộc trò chuyện
function resetChat() {
    // Xóa tất cả tin nhắn trừ typingContainer
    const messages = chatMessages.querySelectorAll('.message:not(#typingContainer)');
    messages.forEach(msg => msg.remove());

    conversationHistory = [];
    localStorage.removeItem('userPronoun');

    // Thêm lại lời chào ban đầu
    appendMessage(WELCOME_MSG, 'assistant');
}

// Khởi chạy lời chào khi vừa vào trang web
document.addEventListener('DOMContentLoaded', () => {
    resetChat();
});