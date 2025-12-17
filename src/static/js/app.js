/**
 * HealthCost AI Copilot - Main Application
 *
 * Handles UI interactions and state management.
 */

// =============================================================================
// State Management
// =============================================================================

const AppState = {
    clients: [],
    selectedClient: null,
    contracts: [],
    selectedContract: null,
    conversations: [],
    selectedConversation: null,
    currentMessages: [],
    isLoading: false,
    isSending: false,
};

// =============================================================================
// DOM Elements
// =============================================================================

const DOM = {
    // Sidebar
    clientsList: document.getElementById('clients-list'),
    contractsSection: document.getElementById('contracts-section'),
    contractsList: document.getElementById('contracts-list'),
    conversationsList: document.getElementById('conversations-list'),

    // Chat
    chatWelcome: document.getElementById('chat-welcome'),
    chatMessages: document.getElementById('chat-messages'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    chatContext: document.getElementById('chat-context'),
    contextClient: document.getElementById('context-client'),
    contextContract: document.getElementById('context-contract'),
    btnSend: document.getElementById('btn-send'),

    // Buttons
    btnNewClient: document.getElementById('btn-new-client'),
    btnUpload: document.getElementById('btn-upload'),
    btnNewChat: document.getElementById('btn-new-chat'),

    // Modals
    modalNewClient: document.getElementById('modal-new-client'),
    modalUpload: document.getElementById('modal-upload'),
    formNewClient: document.getElementById('form-new-client'),

    // Upload
    uploadDropzone: document.getElementById('upload-dropzone'),
    fileInput: document.getElementById('file-input'),
    uploadPreview: document.getElementById('upload-preview'),
    uploadProgress: document.getElementById('upload-progress'),
    progressFill: document.getElementById('progress-fill'),
    progressStatus: document.getElementById('progress-status'),
    progressPercent: document.getElementById('progress-percent'),
    btnStartUpload: document.getElementById('btn-start-upload'),
    btnRemoveFile: document.getElementById('btn-remove-file'),
    fileName: document.getElementById('file-name'),
    fileSize: document.getElementById('file-size'),
    dropzoneHint: document.getElementById('dropzone-hint'),

    // Toast
    toastContainer: document.getElementById('toast-container'),
};

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Format file size to human readable
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return 'Hoje';
    if (days === 1) return 'Ontem';
    if (days < 7) return `${days} dias atras`;

    return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: 'short',
    });
}

/**
 * Group conversations by date
 */
function groupConversationsByDate(conversations) {
    const groups = {};

    conversations.forEach(conv => {
        const date = formatDate(conv.updated_at || conv.created_at);
        if (!groups[date]) groups[date] = [];
        groups[date].push(conv);
    });

    return groups;
}

/**
 * Auto-resize textarea
 */
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

/**
 * Escape HTML for safe rendering
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================================================
// Toast Notifications
// =============================================================================

function showToast(type, title, message = '') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
        error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    };

    toast.innerHTML = `
        <div class="toast-icon">${icons[type]}</div>
        <div class="toast-content">
            <div class="toast-title">${escapeHtml(title)}</div>
            ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ''}
        </div>
    `;

    DOM.toastContainer.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.classList.add('toast-out');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// =============================================================================
// Modal Management
// =============================================================================

function openModal(modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
}

function setupModals() {
    // Close modal on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeModal(overlay);
            }
        });
    });

    // Close modal on button click
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modal = btn.closest('.modal-overlay');
            closeModal(modal);
        });
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.active').forEach(closeModal);
        }
    });
}

// =============================================================================
// Clients
// =============================================================================

async function loadClients() {
    try {
        const response = await API.Clients.list();
        AppState.clients = response.clients || [];
        renderClients();
    } catch (error) {
        showToast('error', 'Erro ao carregar clientes', error.message);
        DOM.clientsList.innerHTML = '<div class="empty-state"><p>Erro ao carregar clientes</p></div>';
    }
}

function renderClients() {
    if (AppState.clients.length === 0) {
        DOM.clientsList.innerHTML = `
            <div class="empty-state">
                <p>Nenhum cliente cadastrado</p>
            </div>
        `;
        return;
    }

    DOM.clientsList.innerHTML = AppState.clients.map(client => `
        <button class="list-item ${AppState.selectedClient?.id === client.id ? 'active' : ''}"
                data-client-id="${client.id}">
            <div class="list-item-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                </svg>
            </div>
            <div class="list-item-content">
                <span class="list-item-title">${escapeHtml(client.name)}</span>
                <span class="list-item-subtitle">${escapeHtml(client.document || '')}</span>
            </div>
        </button>
    `).join('');

    // Add click handlers
    DOM.clientsList.querySelectorAll('.list-item').forEach(item => {
        item.addEventListener('click', () => {
            const clientId = item.dataset.clientId;
            selectClient(AppState.clients.find(c => c.id === clientId));
        });
    });
}

async function selectClient(client) {
    if (!client) return;

    AppState.selectedClient = client;
    AppState.selectedContract = null;
    AppState.selectedConversation = null;
    AppState.currentMessages = [];

    // Update UI
    renderClients();
    showChatWelcome();
    updateChatContext();
    enableChatInput();

    // Load client data
    await Promise.all([
        loadContracts(client.id),
        loadConversations(client.id),
    ]);
}

async function createClient(data) {
    try {
        const client = await API.Clients.create(data);
        AppState.clients.unshift(client);
        renderClients();
        selectClient(client);
        showToast('success', 'Cliente criado', client.name);
        return client;
    } catch (error) {
        showToast('error', 'Erro ao criar cliente', error.message);
        throw error;
    }
}

// =============================================================================
// Contracts
// =============================================================================

async function loadContracts(clientId) {
    try {
        const response = await API.Clients.getContracts(clientId);
        AppState.contracts = response.contracts || [];
        renderContracts();
    } catch (error) {
        console.error('Error loading contracts:', error);
        AppState.contracts = [];
        renderContracts();
    }
}

function renderContracts() {
    DOM.contractsSection.style.display = 'block';

    if (AppState.contracts.length === 0) {
        DOM.contractsList.innerHTML = `
            <div class="empty-state">
                <p>Nenhum contrato</p>
            </div>
        `;
        return;
    }

    DOM.contractsList.innerHTML = AppState.contracts.map(contract => `
        <button class="list-item ${AppState.selectedContract?.id === contract.id ? 'active' : ''}"
                data-contract-id="${contract.id}">
            <div class="list-item-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
            </div>
            <div class="list-item-content">
                <span class="list-item-title">${escapeHtml(contract.filename || contract.id)}</span>
                <span class="list-item-subtitle">${contract.status || 'uploaded'}</span>
            </div>
        </button>
    `).join('');

    // Add click handlers
    DOM.contractsList.querySelectorAll('.list-item').forEach(item => {
        item.addEventListener('click', () => {
            const contractId = item.dataset.contractId;
            const contract = AppState.contracts.find(c => c.id === contractId);

            // Toggle selection
            if (AppState.selectedContract?.id === contractId) {
                AppState.selectedContract = null;
            } else {
                AppState.selectedContract = contract;
            }

            renderContracts();
            updateChatContext();
        });
    });
}

// =============================================================================
// Conversations
// =============================================================================

async function loadConversations(clientId) {
    try {
        const response = await API.Conversations.list(clientId);
        AppState.conversations = response.conversations || [];
        renderConversations();
    } catch (error) {
        console.error('Error loading conversations:', error);
        AppState.conversations = [];
        renderConversations();
    }
}

function renderConversations() {
    if (!AppState.selectedClient) {
        DOM.conversationsList.innerHTML = `
            <div class="empty-state">
                <p>Selecione um cliente para ver as conversas</p>
            </div>
        `;
        return;
    }

    if (AppState.conversations.length === 0) {
        DOM.conversationsList.innerHTML = `
            <div class="empty-state">
                <p>Nenhuma conversa ainda</p>
            </div>
        `;
        return;
    }

    const grouped = groupConversationsByDate(AppState.conversations);
    let html = '';

    for (const [date, convs] of Object.entries(grouped)) {
        html += `<div class="conversation-group">
            <div class="conversation-group-title">${date}</div>
            ${convs.map(conv => `
                <button class="list-item ${AppState.selectedConversation?.id === conv.id ? 'active' : ''}"
                        data-conversation-id="${conv.id}">
                    <div class="list-item-content">
                        <span class="list-item-title">${escapeHtml(conv.title || 'Nova conversa')}</span>
                        <span class="list-item-subtitle">${conv.message_count || 0} mensagens</span>
                    </div>
                </button>
            `).join('')}
        </div>`;
    }

    DOM.conversationsList.innerHTML = html;

    // Add click handlers
    DOM.conversationsList.querySelectorAll('.list-item').forEach(item => {
        item.addEventListener('click', () => {
            const conversationId = item.dataset.conversationId;
            selectConversation(AppState.conversations.find(c => c.id === conversationId));
        });
    });
}

async function selectConversation(conversation) {
    if (!conversation) return;

    AppState.selectedConversation = conversation;
    renderConversations();

    // Load conversation messages
    try {
        const detail = await API.Conversations.get(conversation.id, AppState.selectedClient.id);
        AppState.currentMessages = detail.messages || [];
        renderMessages();
        showChatMessages();
    } catch (error) {
        showToast('error', 'Erro ao carregar conversa', error.message);
    }
}

function startNewConversation() {
    AppState.selectedConversation = null;
    AppState.currentMessages = [];
    renderConversations();
    showChatWelcome();
}

// =============================================================================
// Chat
// =============================================================================

function showChatWelcome() {
    DOM.chatWelcome.style.display = 'flex';
    DOM.chatMessages.style.display = 'none';
}

function showChatMessages() {
    DOM.chatWelcome.style.display = 'none';
    DOM.chatMessages.style.display = 'flex';
    scrollToBottom();
}

function updateChatContext() {
    const container = DOM.chatContext.parentElement;

    if (AppState.selectedClient) {
        container.classList.add('has-context');
        DOM.contextClient.textContent = AppState.selectedClient.name;
        DOM.contextContract.textContent = AppState.selectedContract
            ? AppState.selectedContract.filename || 'Contrato selecionado'
            : 'Todos os contratos';
    } else {
        container.classList.remove('has-context');
    }
}

function enableChatInput() {
    DOM.chatInput.disabled = false;
    DOM.chatInput.placeholder = 'Digite sua pergunta sobre contratos, custos ou renegociacao...';
    updateSendButton();
}

function disableChatInput() {
    DOM.chatInput.disabled = true;
    DOM.chatInput.placeholder = 'Selecione um cliente para comecar...';
    DOM.btnSend.disabled = true;
}

function updateSendButton() {
    DOM.btnSend.disabled = !DOM.chatInput.value.trim() || AppState.isSending;
}

function renderMessages() {
    DOM.chatMessages.innerHTML = AppState.currentMessages.map((msg, index) => {
        const isUser = msg.role === 'user';
        const avatar = isUser
            ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
            : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>';

        let content = isUser ? escapeHtml(msg.content) : marked.parse(msg.content);

        // Add sources if available (deduplicated and grouped)
        let sourcesHtml = '';
        if (!isUser && msg.metadata?.sources?.length > 0) {
            // Deduplicate sources by document + section
            const uniqueSources = [];
            const seen = new Set();
            for (const s of msg.metadata.sources) {
                const key = `${s.document_name || s.document_id}|${s.section_title || ''}|${s.page_number || ''}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    uniqueSources.push(s);
                }
            }

            // Limit to top 5 unique sources
            const displaySources = uniqueSources.slice(0, 5);

            sourcesHtml = `
                <div class="message-sources">
                    <div class="sources-title">Fontes</div>
                    ${displaySources.map(s => {
                        const docName = escapeHtml(s.document_name || 'Documento');
                        const section = s.section_title ? ` - ${escapeHtml(s.section_title)}` : '';
                        const page = s.page_number ? ` (p.${s.page_number})` : '';
                        return `
                        <span class="source-item">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            </svg>
                            ${docName}${section}${page}
                        </span>
                    `}).join('')}
                </div>
            `;
        }

        // Delete button (only show for messages with ID from backend)
        const messageId = msg.id;
        const deleteBtn = messageId ? `
            <button class="message-delete-btn" onclick="deleteMessage('${messageId}', ${index})" title="Excluir mensagem">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button>
        ` : '';

        return `
            <div class="message message-${isUser ? 'user' : 'assistant'}" data-message-id="${messageId || ''}">
                <div class="message-avatar">${avatar}</div>
                <div class="message-content">
                    ${content}
                    ${sourcesHtml}
                </div>
                ${deleteBtn}
            </div>
        `;
    }).join('');

    scrollToBottom();
}

async function deleteMessage(messageId, index) {
    if (!AppState.selectedConversation || !AppState.selectedClient) {
        showToast('error', 'Erro', 'Nenhuma conversa selecionada');
        return;
    }

    // Confirmar exclusão
    if (!confirm('Deseja realmente excluir esta mensagem?')) {
        return;
    }

    try {
        await API.Conversations.deleteMessage(
            AppState.selectedConversation.id,
            messageId,
            AppState.selectedClient.id
        );

        // Remover do array local
        AppState.currentMessages.splice(index, 1);
        renderMessages();

        showToast('success', 'Mensagem excluída', 'A mensagem foi removida com sucesso');
    } catch (error) {
        showToast('error', 'Erro ao excluir', error.message);
    }
}

function addMessage(role, content, metadata = {}) {
    AppState.currentMessages.push({ role, content, metadata });
    renderMessages();
}

function addTypingIndicator(initialStatus = null) {
    const indicator = document.createElement('div');
    indicator.className = 'message message-assistant';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = `
        <div class="message-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
            </svg>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-status">${initialStatus || ''}</div>
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        </div>
    `;
    DOM.chatMessages.appendChild(indicator);
    scrollToBottom();
}

function updateTypingStatus(statusMessage) {
    const statusEl = document.querySelector('#typing-indicator .typing-status');
    if (statusEl) {
        statusEl.textContent = statusMessage;
        statusEl.style.display = statusMessage ? 'block' : 'none';
        scrollToBottom();
    }
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

function scrollToBottom() {
    DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
}

async function sendMessage() {
    const message = DOM.chatInput.value.trim();
    if (!message || !AppState.selectedClient || AppState.isSending) return;

    AppState.isSending = true;
    DOM.chatInput.value = '';
    autoResize(DOM.chatInput);
    updateSendButton();

    // Show chat area if on welcome screen
    if (DOM.chatWelcome.style.display !== 'none') {
        showChatMessages();
    }

    // Add user message
    addMessage('user', message);
    addTypingIndicator('Processando...');

    // Use streaming for real-time status updates
    API.Chat.sendMessageStream(message, AppState.selectedClient.id, {
        contractId: AppState.selectedContract?.id,
        conversationId: AppState.selectedConversation?.id,
        includeSources: true,

        // Status update callback
        onStatus: (step, statusMessage, agent) => {
            updateTypingStatus(statusMessage);
        },

        // Completion callback
        onComplete: async (response) => {
            removeTypingIndicator();

            // Add assistant response
            addMessage('assistant', response.response, {
                sources: response.sources,
                executionId: response.execution_id,
            });

            // Update conversation ID if new
            if (!AppState.selectedConversation && response.conversation_id) {
                AppState.selectedConversation = { id: response.conversation_id };
                // Reload conversations to get the new one
                await loadConversations(AppState.selectedClient.id);
            }

            AppState.isSending = false;
            updateSendButton();
        },

        // Error callback
        onError: (error) => {
            removeTypingIndicator();
            showToast('error', 'Erro ao enviar mensagem', error.message || 'Erro desconhecido');
            AppState.isSending = false;
            updateSendButton();
        },
    });
}

// =============================================================================
// Upload
// =============================================================================

let uploadState = {
    file: null,
    type: 'contract',
};

function setupUpload() {
    // Type selector
    document.querySelectorAll('.upload-type-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.upload-type-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            uploadState.type = btn.dataset.type;

            // Update hint text
            DOM.dropzoneHint.textContent = uploadState.type === 'contract'
                ? 'PDF ate 50MB'
                : 'CSV ou Excel ate 50MB';

            // Update accepted file types
            DOM.fileInput.accept = uploadState.type === 'contract'
                ? '.pdf'
                : '.csv,.xls,.xlsx';
        });
    });

    // Dropzone click
    DOM.uploadDropzone.addEventListener('click', () => {
        DOM.fileInput.click();
    });

    // File input change
    DOM.fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            selectFile(e.target.files[0]);
        }
    });

    // Drag and drop
    DOM.uploadDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        DOM.uploadDropzone.classList.add('dragover');
    });

    DOM.uploadDropzone.addEventListener('dragleave', () => {
        DOM.uploadDropzone.classList.remove('dragover');
    });

    DOM.uploadDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        DOM.uploadDropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            selectFile(e.dataTransfer.files[0]);
        }
    });

    // Remove file
    DOM.btnRemoveFile.addEventListener('click', () => {
        resetUpload();
    });

    // Start upload
    DOM.btnStartUpload.addEventListener('click', () => {
        startUpload();
    });
}

function selectFile(file) {
    uploadState.file = file;

    // Show preview
    DOM.uploadDropzone.style.display = 'none';
    DOM.uploadPreview.style.display = 'block';
    DOM.fileName.textContent = file.name;
    DOM.fileSize.textContent = formatFileSize(file.size);
    DOM.btnStartUpload.disabled = false;
}

function resetUpload() {
    uploadState.file = null;
    DOM.fileInput.value = '';
    DOM.uploadDropzone.style.display = 'block';
    DOM.uploadPreview.style.display = 'none';
    DOM.uploadProgress.style.display = 'none';
    DOM.btnStartUpload.disabled = true;

    // Reset progress steps
    document.querySelectorAll('.progress-step').forEach(step => {
        step.classList.remove('active', 'completed');
    });
}

async function startUpload() {
    if (!uploadState.file || !AppState.selectedClient) {
        showToast('error', 'Erro', 'Selecione um cliente e um arquivo');
        return;
    }

    // Show progress
    DOM.uploadPreview.style.display = 'none';
    DOM.uploadProgress.style.display = 'block';
    DOM.btnStartUpload.disabled = true;

    // Set first step active
    setProgressStep('upload');

    try {
        // Upload with progress
        const uploadResponse = await API.Upload.uploadWithProgress(
            uploadState.file,
            AppState.selectedClient.id,
            uploadState.type,
            {
                onProgress: (percent) => {
                    DOM.progressFill.style.width = `${percent}%`;
                    DOM.progressPercent.textContent = `${percent}%`;
                },
            }
        );

        // Get document_id from upload response
        const documentId = uploadResponse.document_id;

        if (!documentId) {
            throw new Error('Documento nao retornou ID');
        }

        // Process the document (extract, chunk, index)
        setProgressStep('processing');
        DOM.progressStatus.textContent = 'Processando documento...';
        DOM.progressFill.style.width = '60%';
        DOM.progressPercent.textContent = '60%';

        let processResponse;
        if (uploadState.type === 'contract') {
            // Process contract: extract text, chunk, generate embeddings, index
            processResponse = await API.Documents.process(documentId, AppState.selectedClient.id);
        } else {
            // Process costs: parse CSV/Excel rows, store in Cosmos DB
            processResponse = await API.Costs.process(documentId, AppState.selectedClient.id);
        }

        if (!processResponse.success) {
            throw new Error(processResponse.error_message || 'Falha no processamento');
        }

        // Indexing complete
        setProgressStep('indexing');
        DOM.progressStatus.textContent = 'Indexando...';
        DOM.progressFill.style.width = '90%';
        DOM.progressPercent.textContent = '90%';
        await sleep(500); // Brief pause for UI feedback

        // Complete
        setProgressStep('complete');
        DOM.progressStatus.textContent = 'Concluido!';
        DOM.progressFill.style.width = '100%';
        DOM.progressPercent.textContent = '100%';

        // Show success message with details
        if (uploadState.type === 'contract') {
            const chunks = processResponse.total_chunks || 0;
            const pages = processResponse.total_pages || 0;
            showToast('success', 'Contrato processado', `${pages} paginas, ${chunks} chunks indexados`);
        } else {
            const rows = processResponse.processed_rows || 0;
            showToast('success', 'Custos processados', `${rows} registros importados`);
        }

        // Refresh contracts list
        if (uploadState.type === 'contract') {
            await loadContracts(AppState.selectedClient.id);
        }

        // Close modal after delay
        setTimeout(() => {
            closeModal(DOM.modalUpload);
            resetUpload();
        }, 1500);

    } catch (error) {
        console.error('Upload/Processing error:', error);
        showToast('error', 'Erro no processamento', error.message);
        resetUpload();
    }
}

function setProgressStep(stepName) {
    const steps = ['upload', 'processing', 'indexing', 'complete'];
    const stepIndex = steps.indexOf(stepName);

    document.querySelectorAll('.progress-step').forEach((step, index) => {
        step.classList.remove('active', 'completed');
        if (index < stepIndex) {
            step.classList.add('completed');
        } else if (index === stepIndex) {
            step.classList.add('active');
        }
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// =============================================================================
// Event Handlers
// =============================================================================

function setupEventHandlers() {
    // New Client button
    DOM.btnNewClient.addEventListener('click', () => {
        openModal(DOM.modalNewClient);
    });

    // Upload button
    DOM.btnUpload.addEventListener('click', () => {
        if (!AppState.selectedClient) {
            showToast('info', 'Selecione um cliente', 'Escolha um cliente antes de fazer upload');
            return;
        }
        openModal(DOM.modalUpload);
    });

    // New Chat button
    DOM.btnNewChat.addEventListener('click', () => {
        startNewConversation();
    });

    // New Client form
    DOM.formNewClient.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = {
            name: formData.get('name'),
            document: formData.get('document'),
            email: formData.get('email') || undefined,
            phone: formData.get('phone') || undefined,
        };

        try {
            await createClient(data);
            closeModal(DOM.modalNewClient);
            e.target.reset();
        } catch (error) {
            // Error already handled in createClient
        }
    });

    // Chat form
    DOM.chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage();
    });

    // Chat input
    DOM.chatInput.addEventListener('input', () => {
        autoResize(DOM.chatInput);
        updateSendButton();
    });

    DOM.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Hint cards
    document.querySelectorAll('.hint-card').forEach(card => {
        card.addEventListener('click', () => {
            if (!AppState.selectedClient) {
                showToast('info', 'Selecione um cliente', 'Escolha um cliente primeiro');
                return;
            }
            DOM.chatInput.value = card.dataset.hint;
            autoResize(DOM.chatInput);
            updateSendButton();
            DOM.chatInput.focus();
        });
    });
}

// =============================================================================
// Initialization
// =============================================================================

async function init() {
    setupModals();
    setupUpload();
    setupEventHandlers();

    // Load initial data
    await loadClients();

    // Disable chat until client is selected
    disableChatInput();
}

// Start app
document.addEventListener('DOMContentLoaded', init);
