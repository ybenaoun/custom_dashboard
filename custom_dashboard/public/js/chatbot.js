/*
    Chatbot Frontend v2.1 — Fix: send button + markdown rendering
*/

(function () {
  "use strict";

  if (window.__chatbot_initialized) return;
  window.__chatbot_initialized = true;

  var LOTTIE_URL = "/assets/custom_dashboard/js/ai-animation-flow-1.json";
  var isOpen = false;
  var currentConversationId = null;
  var sidebarOpen = false;

  // ─── Simple Markdown → HTML parser ───
  function renderMarkdown(text) {
    if (!text) return "";
    var html = text;
    // Escape HTML
    html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    // Bold **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");
    // Italic *text* or _text_
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    html = html.replace(/_(.+?)_/g, "<em>$1</em>");
    // Inline code `text`
    html = html.replace(/`(.+?)`/g, '<code style="background:#f0f2f5;padding:1px 4px;border-radius:3px;font-size:12px;">$1</code>');

    // P12 — Markdown tables
    html = html.replace(/(?:^|\n)((?:\|.+\|(?:\n|$))+)/g, function(match) {
      var rows = match.trim().split('\n').filter(function(r) { return r.trim(); });
      if (rows.length < 2) return match;
      // Check if 2nd row is separator (|---|---|)
      var isSep = /^\|[\s\-:]+(\|[\s\-:]+)+\|?$/.test(rows[1]);
      var headerRow = rows[0];
      var dataRows = isSep ? rows.slice(2) : rows.slice(1);

      function parseCells(row) {
        return row.split('|').filter(function(c, i, a) {
          return i > 0 && i < a.length - 1;
        }).map(function(c) { return c.trim(); });
      }

      var table = '<div class="chatbot-table-wrapper"><table>';
      if (isSep) {
        var headers = parseCells(headerRow);
        table += '<thead><tr>';
        headers.forEach(function(h) { table += '<th>' + h + '</th>'; });
        table += '</tr></thead>';
      }
      table += '<tbody>';
      if (!isSep) {
        var firstCells = parseCells(headerRow);
        table += '<tr>';
        firstCells.forEach(function(c) { table += '<td>' + c + '</td>'; });
        table += '</tr>';
      }
      dataRows.forEach(function(row) {
        var cells = parseCells(row);
        table += '<tr>';
        cells.forEach(function(c) { table += '<td>' + c + '</td>'; });
        table += '</tr>';
      });
      table += '</tbody></table></div>';
      return table;
    });

    // Unordered lists (- item)
    html = html.replace(/^[\s]*[-•]\s+(.+)/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/gs, function(match) {
      return '<ul style="margin:6px 0;padding-left:18px;list-style:disc;">' + match + '</ul>';
    });
    // Fix nested <ul> (consecutive <li> already wrapped)
    html = html.replace(/<\/ul>\s*<ul[^>]*>/g, '');
    // Numbered lists (1. item)
    html = html.replace(/^\s*\d+\.\s+(.+)/gm, '<li>$1</li>');
    // Line breaks
    html = html.replace(/\n\n/g, '<br><br>');
    html = html.replace(/\n/g, '<br>');
    // Clean up extra <br> inside lists
    html = html.replace(/<br>\s*<li>/g, '<li>');
    html = html.replace(/<\/li>\s*<br>/g, '</li>');
    // Clean up <br> inside tables
    html = html.replace(/<br>\s*<table/g, '<table');
    html = html.replace(/<\/table>\s*<br>/g, '</table>');
    html = html.replace(/<br>\s*<div class="chatbot-table-wrapper">/g, '<div class="chatbot-table-wrapper">');
    return html;
  }

  function createChatbotDOM() {
    var fab = document.createElement("div");
    fab.className = "chatbot-fab";
    fab.id = "chatbotFab";
    fab.title = "AI Assistant";
    fab.innerHTML =
      '<div class="lottie-container" id="chatbotLottie"></div>' +
      '<svg class="fab-close-icon" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round">' +
        '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>' +
      '</svg>';

    var win = document.createElement("div");
    win.className = "chatbot-window";
    win.id = "chatbotWindow";
    win.innerHTML =
      '<div class="chatbot-sidebar" id="chatbotSidebar">' +
        '<div class="chatbot-sidebar-header">' +
          '<h4>Conversations</h4>' +
          '<button class="chatbot-sidebar-close" id="chatbotSidebarClose" title="Fermer">' +
            '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>' +
          '</button>' +
        '</div>' +
        '<button class="chatbot-new-conv-btn" id="chatbotNewConv">' +
          '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>' +
          '<span>Nouvelle conversation</span>' +
        '</button>' +
        '<div class="chatbot-conv-list" id="chatbotConvList"></div>' +
      '</div>' +
      '<div class="chatbot-main">' +
        '<div class="chatbot-header">' +
          '<button class="chatbot-menu-btn" id="chatbotMenuBtn" title="Conversations">' +
            '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>' +
          '</button>' +
          '<div class="chatbot-header-avatar"><div class="chatbot-header-lottie" id="chatbotHeaderLottie"></div></div>' +
          '<div class="chatbot-header-info">' +
            '<h3 id="chatbotHeaderTitle">AI Assistant</h3>' +
            '<div class="chatbot-header-status"><div class="status-dot"></div><span>En ligne</span></div>' +
          '</div>' +
          '<button class="chatbot-voice-toggle" id="chatbotVoiceToggle" title="Lecture vocale auto">' +
            '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4.03v8.05A4.5 4.5 0 0 0 16.5 12zM14 3.23v2.06a7 7 0 0 1 0 13.42v2.06A9 9 0 0 0 14 3.23z"/></svg>' +
          '</button>' +
          '<button class="chatbot-header-close" id="chatbotClose" title="Fermer">' +
            '<svg viewBox="0 0 24 24"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>' +
          '</button>' +
        '</div>' +
        '<div class="chatbot-messages" id="chatbotMessages">' +
          '<div class="chatbot-welcome"><div class="chatbot-welcome-icon"><div class="chatbot-welcome-lottie" id="chatbotWelcomeLottie"></div></div>' +
          '<h4>Bienvenue ! 👋</h4><p>Je suis votre assistant AI. Comment puis-je vous aider aujourd\'hui ?</p></div>' +
        '</div>' +
        '<div class="chatbot-input-area">' +
          '<button class="chatbot-mic-btn" id="chatbotMic" title="Parler"><svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/></svg></button>' +
          '<input type="text" class="chatbot-input" id="chatbotInput" placeholder="Écrivez votre message..." autocomplete="off" />' +
          '<button class="chatbot-send-btn" id="chatbotSend" title="Envoyer"><svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>' +
        '</div>' +
      '</div>' +
      '<div class="chatbot-modal-overlay" id="chatbotModalOverlay">' +
        '<div class="chatbot-modal">' +
          '<div class="chatbot-modal-icon chatbot-modal-icon-danger">' +
            '<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#e74c3c" stroke-width="1.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>' +
          '</div>' +
          '<h4>Supprimer la conversation ?</h4>' +
          '<p id="chatbotModalText">Cette action est irréversible.</p>' +
          '<div class="chatbot-modal-actions">' +
            '<button class="chatbot-modal-cancel" id="chatbotModalCancel">Annuler</button>' +
            '<button class="chatbot-modal-confirm chatbot-modal-confirm-red" id="chatbotModalConfirm">Supprimer</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="chatbot-modal-overlay" id="chatbotRenameOverlay">' +
        '<div class="chatbot-modal">' +
          '<div class="chatbot-modal-icon chatbot-modal-icon-blue">' +
            '<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#1B84FF" stroke-width="1.5"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>' +
          '</div>' +
          '<h4>Renommer la conversation</h4>' +
          '<input type="text" class="chatbot-modal-input" id="chatbotRenameInput" placeholder="Nouveau titre..." />' +
          '<div class="chatbot-modal-actions">' +
            '<button class="chatbot-modal-cancel" id="chatbotRenameCancel">Annuler</button>' +
            '<button class="chatbot-modal-confirm chatbot-modal-confirm-blue" id="chatbotRenameConfirm">Renommer</button>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.body.appendChild(fab);
    document.body.appendChild(win);
    return { fab: fab, win: win };
  }

  function init() {
    var refs = createChatbotDOM();
    var fab = refs.fab, win = refs.win;

    var closeBtn = win.querySelector("#chatbotClose");
    var messagesEl = win.querySelector("#chatbotMessages");
    var inputEl = win.querySelector("#chatbotInput");
    var sendBtn = win.querySelector("#chatbotSend");
    var menuBtn = win.querySelector("#chatbotMenuBtn");
    var sidebar = win.querySelector("#chatbotSidebar");
    var sidebarCloseBtn = win.querySelector("#chatbotSidebarClose");
    var newConvBtn = win.querySelector("#chatbotNewConv");
    var convListEl = win.querySelector("#chatbotConvList");
    var headerTitle = win.querySelector("#chatbotHeaderTitle");
    var lottieContainer = fab.querySelector("#chatbotLottie");
    var headerLottieContainer = win.querySelector("#chatbotHeaderLottie");
    var welcomeLottieContainer = win.querySelector("#chatbotWelcomeLottie");

    var modalOverlay = win.querySelector("#chatbotModalOverlay");
    var modalCancel = win.querySelector("#chatbotModalCancel");
    var modalConfirm = win.querySelector("#chatbotModalConfirm");
    var modalText = win.querySelector("#chatbotModalText");
    var pendingDeleteId = null;

    var renameOverlay = win.querySelector("#chatbotRenameOverlay");
    var renameInput = win.querySelector("#chatbotRenameInput");
    var renameCancel = win.querySelector("#chatbotRenameCancel");
    var renameConfirm = win.querySelector("#chatbotRenameConfirm");
    var pendingRenameId = null;

    var micBtn = win.querySelector("#chatbotMic");
    var voiceToggleBtn = win.querySelector("#chatbotVoiceToggle");

    // ─── Lottie ───
    function initLottie() {
      try { lottie.loadAnimation({ container: lottieContainer, renderer: "svg", loop: true, autoplay: true, path: LOTTIE_URL }); } catch (e) { fallbackIcon(lottieContainer); }
      try { lottie.loadAnimation({ container: headerLottieContainer, renderer: "svg", loop: true, autoplay: true, path: LOTTIE_URL }); } catch (e) {}
      try { lottie.loadAnimation({ container: welcomeLottieContainer, renderer: "svg", loop: true, autoplay: true, path: LOTTIE_URL }); } catch (e) {}
    }
   if (typeof lottie !== "undefined") { initLottie(); }
    else {
      var s = document.createElement("script");
      s.src = "/assets/custom_dashboard/js/lottie.min.js";
      s.onload = initLottie;
      s.onerror = function () { fallbackIcon(lottieContainer); };
      document.head.appendChild(s);
    }
    function fallbackIcon(c) {
      c.innerHTML = '<svg viewBox="0 0 24 24" fill="#fff" width="32" height="32"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>';
    }

    // ─── Toggle Chat ───
    function toggleChat() {
      isOpen = !isOpen;
      fab.classList.toggle("active", isOpen);
      win.classList.toggle("open", isOpen);
      if (isOpen) {
        setTimeout(function () { inputEl.focus(); }, 350);
        loadConversations();
      }
    }
    fab.addEventListener("click", toggleChat);
    closeBtn.addEventListener("click", toggleChat);

    // ─── Sidebar ───
    function openSidebar() { sidebarOpen = true; sidebar.classList.add("open"); win.classList.add("sidebar-visible"); }
    function closeSidebar() { sidebarOpen = false; sidebar.classList.remove("open"); win.classList.remove("sidebar-visible"); }
    menuBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (sidebarOpen) closeSidebar(); else { openSidebar(); loadConversations(); }
    });
    sidebarCloseBtn.addEventListener("click", function (e) { e.stopPropagation(); closeSidebar(); });

    // ─── Delete Modal ───
    function showDeleteModal(id, title) {
      pendingDeleteId = id;
      modalText.textContent = 'Supprimer "' + title + '" ? Cette action est irréversible.';
      modalOverlay.classList.add("visible");
    }
    function hideDeleteModal() { modalOverlay.classList.remove("visible"); pendingDeleteId = null; }
    modalCancel.addEventListener("click", hideDeleteModal);
    modalOverlay.addEventListener("click", function (e) { if (e.target === modalOverlay) hideDeleteModal(); });
    modalConfirm.addEventListener("click", function () {
      if (!pendingDeleteId) return;
      var id = pendingDeleteId; hideDeleteModal();
      frappe.call({ method: "custom_dashboard.chatbot.chatbot_api.delete_conversation", args: { conversation_id: id },
        callback: function () { if (currentConversationId === id) startNewConversation(); loadConversations(); }
      });
    });

    // ─── Rename Modal ───
    function showRenameModal(id, title) {
      pendingRenameId = id; renameInput.value = title; renameOverlay.classList.add("visible");
      setTimeout(function () { renameInput.focus(); renameInput.select(); }, 100);
    }
    function hideRenameModal() { renameOverlay.classList.remove("visible"); pendingRenameId = null; }
    renameCancel.addEventListener("click", hideRenameModal);
    renameOverlay.addEventListener("click", function (e) { if (e.target === renameOverlay) hideRenameModal(); });
    renameInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); renameConfirm.click(); }
      if (e.key === "Escape") hideRenameModal();
    });
    renameConfirm.addEventListener("click", function () {
      if (!pendingRenameId) return;
      var t = renameInput.value.trim(); if (!t) return;
      var id = pendingRenameId; hideRenameModal();
      frappe.call({ method: "custom_dashboard.chatbot.chatbot_api.rename_conversation", args: { conversation_id: id, new_title: t },
        callback: function () { if (currentConversationId === id) headerTitle.textContent = t; loadConversations(); }
      });
    });

    // ─── Conversations ───
    function loadConversations() {
      frappe.call({ method: "custom_dashboard.chatbot.chatbot_api.get_conversations",
        callback: function (r) { if (r && r.message) renderConversationList(r.message); },
        error: function () { convListEl.innerHTML = '<div class="chatbot-conv-empty">Erreur de chargement</div>'; }
      });
    }

    function renderConversationList(conversations) {
      convListEl.innerHTML = "";
      if (!conversations.length) { convListEl.innerHTML = '<div class="chatbot-conv-empty">Aucune conversation</div>'; return; }
      conversations.forEach(function (conv) {
        var item = document.createElement("div");
        item.className = "chatbot-conv-item" + (conv.name === currentConversationId ? " active" : "");
        item.dataset.id = conv.name;
        var timeStr = conv.last_message_at ? formatTimeAgo(conv.last_message_at) : "";
        item.innerHTML =
          '<div class="chatbot-conv-item-content">' +
            '<div class="chatbot-conv-item-title">' + escapeHtml(conv.title) + '</div>' +
            '<div class="chatbot-conv-item-time">' + timeStr + '</div>' +
          '</div>' +
          '<div class="chatbot-conv-actions">' +
            '<button class="chatbot-conv-action-btn chatbot-conv-rename" title="Renommer">' +
              '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>' +
            '</button>' +
            '<button class="chatbot-conv-action-btn chatbot-conv-delete" title="Supprimer">' +
              '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>' +
            '</button>' +
          '</div>';
        item.querySelector(".chatbot-conv-item-content").addEventListener("click", function () { loadConversation(conv.name, conv.title); });
        item.querySelector(".chatbot-conv-rename").addEventListener("click", function (e) { e.stopPropagation(); showRenameModal(conv.name, conv.title); });
        item.querySelector(".chatbot-conv-delete").addEventListener("click", function (e) { e.stopPropagation(); showDeleteModal(conv.name, conv.title); });
        convListEl.appendChild(item);
      });
    }

    function loadConversation(convId, title) {
      currentConversationId = convId;
      headerTitle.textContent = title || "AI Assistant";
      messagesEl.innerHTML = '<div class="chatbot-loading">Chargement...</div>';
      convListEl.querySelectorAll(".chatbot-conv-item").forEach(function (el) { el.classList.toggle("active", el.dataset.id === convId); });
      frappe.call({ method: "custom_dashboard.chatbot.chatbot_api.get_messages", args: { conversation_id: convId },
        callback: function (r) {
          messagesEl.innerHTML = "";
          if (r && r.message && r.message.length) {
            r.message.forEach(function (msg) { addMessage(msg.content, msg.role); });
          } else { showWelcome(); }
        },
        error: function () { messagesEl.innerHTML = ""; addMessage("Erreur lors du chargement.", "bot"); }
      });
    }

    newConvBtn.addEventListener("click", function () { startNewConversation(); });

    function startNewConversation() {
      currentConversationId = null; headerTitle.textContent = "AI Assistant";
      messagesEl.innerHTML = ""; showWelcome(); inputEl.focus();
      convListEl.querySelectorAll(".chatbot-conv-item").forEach(function (el) { el.classList.remove("active"); });
    }

    function showWelcome() {
      var d = document.createElement("div"); d.className = "chatbot-welcome";
      d.innerHTML = '<div class="chatbot-welcome-icon"><div class="chatbot-welcome-lottie"></div></div><h4>Bienvenue ! 👋</h4><p>Je suis votre assistant AI. Comment puis-je vous aider aujourd\'hui ?</p>';
      messagesEl.appendChild(d);
      try { if (typeof lottie !== "undefined") lottie.loadAnimation({ container: d.querySelector(".chatbot-welcome-lottie"), renderer: "svg", loop: true, autoplay: true, path: LOTTIE_URL }); } catch (e) {}
    }

    function frappeCallPromise(method, args) {
      return new Promise(function (resolve, reject) {
        frappe.call({
          method: method,
          args: args || {},
          callback: function (r) { resolve(r ? r.message : null); },
          error: function (err) { reject(err); }
        });
      });
    }

    // ─── Voice: TTS auto-speak + STT mic ───
    var VOICE_PREF_KEY = "chatbot_voice_autospeak";
    var voiceAutoSpeak = (function () {
      try { var v = localStorage.getItem(VOICE_PREF_KEY); return v === null ? true : v === "1"; }
      catch (e) { return true; }
    })();
    var voiceSession = null;            // { fastapi_url, tts_endpoint, stt_endpoint, token, fetched_at, expires_in }
    var currentTtsAudio = null;         // currently playing HTMLAudioElement
    var currentTtsBtn = null;
    var mediaRecorder = null;
    var recordedChunks = [];
    var recordingStream = null;

    function applyVoiceToggleUI() {
      if (!voiceToggleBtn) return;
      voiceToggleBtn.classList.toggle("muted", !voiceAutoSpeak);
      voiceToggleBtn.title = voiceAutoSpeak ? "Lecture vocale: ON" : "Lecture vocale: OFF";
    }
    applyVoiceToggleUI();

    function ensureVoiceSession() {
      var ttl = (voiceSession && voiceSession.expires_in) || 60;
      var fresh = voiceSession && (Date.now() - voiceSession.fetched_at) < (ttl - 5) * 1000;
      if (fresh) return Promise.resolve(voiceSession);
      return frappeCallPromise("custom_dashboard.chatbot.chatbot_proxy.voice_session", {})
        .then(function (sess) {
          if (!sess || !sess.token) throw new Error("Session vocale indisponible.");
          sess.fetched_at = Date.now();
          voiceSession = sess;
          return sess;
        });
    }

    function stripMarkdownForTts(text) {
      if (!text) return "";
      return String(text)
        .replace(/```[\s\S]*?```/g, "")
        .replace(/`([^`]+)`/g, "$1")
        .replace(/\*\*([^*]+)\*\*/g, "$1")
        .replace(/__([^_]+)__/g, "$1")
        .replace(/\*([^*]+)\*/g, "$1")
        .replace(/_([^_]+)_/g, "$1")
        .replace(/^[\s]*[-•]\s+/gm, "")
        .replace(/^\s*\d+\.\s+/gm, "")
        .replace(/\|/g, " ")
        .replace(/\[source\s*\d+\]/gi, "")
        .replace(/\s+/g, " ")
        .trim();
    }

    function stopCurrentTts() {
      if (currentTtsAudio) {
        try { currentTtsAudio.pause(); } catch (e) {}
        try { URL.revokeObjectURL(currentTtsAudio.src); } catch (e) {}
        currentTtsAudio = null;
      }
      if (currentTtsBtn) {
        currentTtsBtn.classList.remove("playing");
        currentTtsBtn = null;
      }
    }

    function speak(text, btn) {
      var clean = stripMarkdownForTts(text);
      if (!clean) return Promise.resolve();
      stopCurrentTts();
      var lang = (frappe && frappe.boot && frappe.boot.lang === "en") ? "en" : "fr";
      return ensureVoiceSession().then(function (sess) {
        var url = String(sess.fastapi_url || "").replace(/\/+$/, "") + (sess.tts_endpoint || "/voice/tts");
        return fetch(url, {
          method: "POST",
          headers: { "Authorization": "Bearer " + sess.token, "Content-Type": "application/json" },
          body: JSON.stringify({ text: clean.slice(0, 3800), language: lang })
        });
      }).then(function (r) {
        if (!r.ok) throw new Error("TTS HTTP " + r.status);
        return r.blob();
      }).then(function (blob) {
        var audio = new Audio(URL.createObjectURL(blob));
        currentTtsAudio = audio;
        currentTtsBtn = btn || null;
        if (btn) btn.classList.add("playing");
        audio.onended = function () { if (currentTtsAudio === audio) stopCurrentTts(); };
        audio.onerror = function () { if (currentTtsAudio === audio) stopCurrentTts(); };
        return audio.play().catch(function (err) {
          // Autoplay may be blocked until first user gesture; that's fine
          stopCurrentTts();
          console.warn("TTS playback blocked:", err);
        });
      }).catch(function (err) {
        console.error("TTS error:", err);
        stopCurrentTts();
      });
    }

    function attachTtsButton(botMsgEl, getText) {
      if (!botMsgEl || botMsgEl.querySelector(".chatbot-msg-tts")) return null;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chatbot-msg-tts";
      btn.title = "Écouter";
      btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4.03v8.05A4.5 4.5 0 0 0 16.5 12z"/></svg>';
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (currentTtsBtn === btn) { stopCurrentTts(); return; }
        speak(getText(), btn);
      });
      botMsgEl.appendChild(btn);
      return btn;
    }

    function maybeAutoSpeak(botMsgEl, text) {
      var btn = attachTtsButton(botMsgEl, function () { return text; });
      if (voiceAutoSpeak && text) speak(text, btn);
    }

    function pickRecorderMime() {
      var candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4", ""];
      for (var i = 0; i < candidates.length; i++) {
        if (!candidates[i]) return "";
        if (window.MediaRecorder && MediaRecorder.isTypeSupported(candidates[i])) return candidates[i];
      }
      return "";
    }

    function startRecording() {
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        addMessage("Microphone non supporté par ce navigateur.", "bot");
        return;
      }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        recordingStream = stream;
        recordedChunks = [];
        var mime = pickRecorderMime();
        try {
          mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        } catch (e) {
          mediaRecorder = new MediaRecorder(stream);
        }
        mediaRecorder.ondataavailable = function (ev) { if (ev.data && ev.data.size) recordedChunks.push(ev.data); };
        mediaRecorder.onstop = function () {
          var blob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
          recordedChunks = [];
          if (recordingStream) {
            recordingStream.getTracks().forEach(function (t) { t.stop(); });
            recordingStream = null;
          }
          micBtn.classList.remove("recording");
          micBtn.classList.add("processing");
          transcribeBlob(blob)
            .then(function (text) {
              if (text) {
                inputEl.value = text;
                updateSendBtn();
                sendMessage();
              }
            })
            .catch(function (err) {
              console.error("STT error:", err);
              addMessage("Transcription vocale indisponible.", "bot");
            })
            .finally(function () { micBtn.classList.remove("processing"); });
        };
        mediaRecorder.start();
        micBtn.classList.add("recording");
        micBtn.title = "Cliquer pour arrêter";
      }).catch(function (err) {
        console.error("getUserMedia error:", err);
        addMessage("Accès au micro refusé.", "bot");
      });
    }

    function stopRecording() {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        try { mediaRecorder.stop(); } catch (e) {}
      }
      micBtn.title = "Parler";
    }

    function transcribeBlob(blob) {
      var lang = (frappe && frappe.boot && frappe.boot.lang === "en") ? "en" : "fr";
      return ensureVoiceSession().then(function (sess) {
        var url = String(sess.fastapi_url || "").replace(/\/+$/, "") + (sess.stt_endpoint || "/voice/stt");
        var ext = (blob.type.indexOf("ogg") !== -1) ? "ogg"
                : (blob.type.indexOf("mp4") !== -1) ? "mp4"
                : "webm";
        var form = new FormData();
        form.append("audio", blob, "voice." + ext);
        form.append("language", lang);
        return fetch(url, {
          method: "POST",
          headers: { "Authorization": "Bearer " + sess.token },
          body: form
        });
      }).then(function (r) {
        if (!r.ok) throw new Error("STT HTTP " + r.status);
        return r.json();
      }).then(function (data) { return (data && data.text) || ""; });
    }

    if (micBtn) {
      micBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        if (mediaRecorder && mediaRecorder.state === "recording") stopRecording();
        else startRecording();
      });
    }
    if (voiceToggleBtn) {
      voiceToggleBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        voiceAutoSpeak = !voiceAutoSpeak;
        try { localStorage.setItem(VOICE_PREF_KEY, voiceAutoSpeak ? "1" : "0"); } catch (err) {}
        applyVoiceToggleUI();
        if (!voiceAutoSpeak) stopCurrentTts();
      });
    }

    function compactMetadata(payload) {
      return {
        model: payload ? payload.model : null,
        input_tokens: payload ? payload.input_tokens : 0,
        output_tokens: payload ? payload.output_tokens : 0,
        rag_confidence: payload ? payload.rag_confidence : null
      };
    }

    function submitFeedback(btn, payload) {
      btn.disabled = true;
      return frappeCallPromise("custom_dashboard.chatbot.chatbot_proxy.submit_feedback", payload)
        .then(function () {
          var group = btn.closest(".chatbot-feedback");
          if (group) {
            group.classList.add("is-sent");
            group.innerHTML = '<span class="chatbot-feedback-sent">Merci pour le retour.</span>';
          }
        })
        .catch(function (err) {
          btn.disabled = false;
          console.error("Chatbot feedback error:", err);
        });
    }

    function addFeedbackControls(botMsg, result, question) {
      if (!botMsg || botMsg.dataset.feedbackAttached === "1") return;
      botMsg.dataset.feedbackAttached = "1";

      var wrap = document.createElement("div");
      wrap.className = "chatbot-feedback";
      wrap.innerHTML =
        '<button class="chatbot-feedback-btn chatbot-feedback-up" title="Reponse correcte" aria-label="Reponse correcte">' +
          '<svg viewBox="0 0 24 24"><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3m0 11V10l5-8a3 3 0 0 1 3 3v4h4a3 3 0 0 1 3 3l-1 6a4 4 0 0 1-4 4H7z"/></svg>' +
        '</button>' +
        '<button class="chatbot-feedback-btn chatbot-feedback-down" title="Reponse incorrecte" aria-label="Reponse incorrecte">' +
          '<svg viewBox="0 0 24 24"><path d="M17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3m0-11v12l-5 8a3 3 0 0 1-3-3v-4H5a3 3 0 0 1-3-3l1-6a4 4 0 0 1 4-4h10z"/></svg>' +
        '</button>';

      function basePayload(rating) {
        return {
          conversation_id: currentConversationId || "",
          question: question || "",
          response: result && result.response ? result.response : botMsg.textContent,
          rating: rating,
          rag_sources: result && result.rag_sources ? JSON.stringify(result.rag_sources) : "[]",
          used_tools: result && result.used_tools ? JSON.stringify(result.used_tools) : "[]",
          metadata: JSON.stringify(compactMetadata(result))
        };
      }

      wrap.querySelector(".chatbot-feedback-up").addEventListener("click", function () {
        submitFeedback(this, basePayload("up"));
      });
      wrap.querySelector(".chatbot-feedback-down").addEventListener("click", function () {
        if (wrap.querySelector(".chatbot-feedback-form")) return;
        var form = document.createElement("div");
        form.className = "chatbot-feedback-form";
        form.innerHTML =
          '<textarea class="chatbot-feedback-text" rows="2" placeholder="Correction attendue ou commentaire..."></textarea>' +
          '<button class="chatbot-feedback-send">Envoyer</button>';
        wrap.appendChild(form);
        var textarea = form.querySelector(".chatbot-feedback-text");
        textarea.focus();
        form.querySelector(".chatbot-feedback-send").addEventListener("click", function () {
          var payload = basePayload("down");
          payload.expected_answer = textarea.value.trim();
          payload.comment = textarea.value.trim();
          submitFeedback(this, payload);
        });
        scrollToBottom();
      });

      botMsg.insertAdjacentElement("afterend", wrap);
      scrollToBottom();
    }

    function setInputEnabled(enabled) {
      inputEl.disabled = !enabled;
      if (enabled) inputEl.focus();
      updateSendBtn();
    }

    function updateBotMessage(el, text) {
      el.innerHTML = renderMarkdown(text || "");
      scrollToBottom();
    }

    function parseSSEBlock(block) {
      var eventName = "message";
      var dataLines = [];
      block.split(/\r?\n/).forEach(function (line) {
        if (line.indexOf("event:") === 0) eventName = line.slice(6).trim();
        else if (line.indexOf("data:") === 0) dataLines.push(line.slice(5).trim());
      });
      if (!dataLines.length) return null;
      var data = {};
      try { data = JSON.parse(dataLines.join("\n")); }
      catch (e) { data = { text: dataLines.join("\n") }; }
      return { event: eventName, data: data };
    }

    function streamChat(prep, typing) {
      var url = String(prep.fastapi_url || "").replace(/\/+$/, "") + (prep.endpoint || "/chat/stream");
      var botMsg = null;
      var finalText = "";
      var donePayload = null;
      var ragSources = [];
      var ragConfidence = null;
      var usedTools = [];

      return fetch(url, {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + prep.token,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(prep.payload)
      }).then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        if (!response.body || !window.TextDecoder) {
          throw new Error("Streaming non supporté par ce navigateur.");
        }

        typing.remove();
        botMsg = addMessage("", "bot");

        var reader = response.body.getReader();
        var decoder = new TextDecoder("utf-8");
        var buffer = "";

        function handleBlock(block) {
          var item = parseSSEBlock(block);
          if (!item) return;
          if (item.event === "token") {
            finalText += item.data.text || "";
            updateBotMessage(botMsg, finalText);
          } else if (item.event === "rag_sources") {
            ragSources = item.data.sources || [];
            ragConfidence = item.data.confidence || null;
          } else if (item.event === "done") {
            donePayload = item.data || {};
            ragSources = donePayload.rag_sources || ragSources;
            ragConfidence = donePayload.rag_confidence || ragConfidence;
            usedTools = donePayload.used_tools || usedTools;
            if (!finalText && donePayload.response) {
              finalText = donePayload.response;
              updateBotMessage(botMsg, finalText);
            }
          } else if (item.event === "error") {
            throw new Error(item.data.message || "Erreur streaming.");
          }
        }

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) {
              buffer += decoder.decode();
              if (buffer.trim()) handleBlock(buffer);
              return donePayload || { response: finalText };
            }
            buffer += decoder.decode(result.value, { stream: true });
            var blocks = buffer.split(/\r?\n\r?\n/);
            buffer = blocks.pop();
            blocks.forEach(handleBlock);
            return pump();
          });
        }

        return pump();
      }).then(function (payload) {
        finalText = finalText || (payload && payload.response) || "";
        if (botMsg && finalText) updateBotMessage(botMsg, finalText);
        if (botMsg && finalText) maybeAutoSpeak(botMsg, finalText);
        return {
          response: finalText,
          model: payload ? payload.model : null,
          input_tokens: payload ? payload.input_tokens : 0,
          output_tokens: payload ? payload.output_tokens : 0,
          rag_sources: ragSources,
          rag_confidence: ragConfidence,
          used_tools: usedTools,
          message_el: botMsg
        };
      });
    }

    function sendMessagePlainV2(text, typing) {
      return frappeCallPromise("custom_dashboard.chatbot.chatbot_proxy.send_message_v2", {
        message: text,
        conversation_id: currentConversationId || ""
      }).then(function (result) {
        typing.remove();
        if (result && result.conversation_id) currentConversationId = result.conversation_id;
        if (result && result.conversation_title) headerTitle.textContent = result.conversation_title;
        var responseText = (result && result.response) || "Erreur.";
        var botMsg = addMessage(responseText, "bot");
        addFeedbackControls(botMsg, result || {}, text);
        if (result && result.response) maybeAutoSpeak(botMsg, result.response);
        loadConversations();
      });
    }

    // ─── Send Message v2 streaming ───
    function sendMessage() {
      var text = inputEl.value.trim();
      if (!text) return;
      var welcome = messagesEl.querySelector(".chatbot-welcome");
      if (welcome) welcome.remove();

      addMessage(text, "user");
      inputEl.value = "";
      setInputEnabled(false);

      var typing = document.createElement("div");
      typing.className = "chatbot-typing";
      typing.innerHTML = "<span></span><span></span><span></span>";
      messagesEl.appendChild(typing);
      scrollToBottom();

      if (!window.fetch || !window.ReadableStream) {
        sendMessagePlainV2(text, typing)
          .catch(function (err) {
            typing.remove();
            console.error("Chatbot v2 fallback error:", err);
            addMessage("Erreur de connexion au service AI.", "bot");
          })
          .finally(function () { setInputEnabled(true); });
        return;
      }

      frappeCallPromise("custom_dashboard.chatbot.chatbot_proxy.prepare_stream_v2", {
        message: text,
        conversation_id: currentConversationId || ""
      }).then(function (prep) {
        if (!prep) throw new Error("Préparation streaming invalide.");
        if (prep.conversation_id) currentConversationId = prep.conversation_id;
        if (prep.conversation_title) headerTitle.textContent = prep.conversation_title;
        return streamChat(prep, typing).then(function (streamResult) {
          return frappeCallPromise("custom_dashboard.chatbot.chatbot_proxy.finish_stream_v2", {
            conversation_id: prep.conversation_id,
            response: streamResult.response || ""
          }).catch(function (err) {
            console.error("Chatbot stream persistence error:", err);
          }).then(function () {
            addFeedbackControls(streamResult.message_el, streamResult, text);
          });
        });
      }).then(function () {
        loadConversations();
      }).catch(function (err) {
        if (typing.parentNode) typing.remove();
        console.error("Chatbot streaming error:", err);
        addMessage("Erreur de connexion au service AI.", "bot");
      }).finally(function () {
        setInputEnabled(true);
      });
    }

    // ─── Add Message (FIX: markdown rendering for bot messages) ───
    function addMessage(text, sender) {
      var msg = document.createElement("div");
      msg.className = "chatbot-msg " + sender;

      if (sender === "bot") {
        // Render markdown for bot messages
        msg.innerHTML = renderMarkdown(text);
      } else {
        // Plain text for user messages
        msg.textContent = text;
      }

      messagesEl.appendChild(msg);
      scrollToBottom();
      return msg;
    }

    function scrollToBottom() {
      requestAnimationFrame(function () { messagesEl.scrollTop = messagesEl.scrollHeight; });
    }

    // ─── Input Events ───
    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });

    // FIX: click + stopPropagation to prevent outside-click handler from closing chat
    sendBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      sendMessage();
    });

    // Also stop propagation on the input area to be safe
    win.querySelector(".chatbot-input-area").addEventListener("click", function (e) {
      e.stopPropagation();
    });

    function updateSendBtn() {
      var hasText = inputEl.value.trim().length > 0;
      sendBtn.classList.toggle("enabled", hasText);
      // Don't set sendBtn.disabled — it blocks click events entirely
    }
    inputEl.addEventListener("input", updateSendBtn);
    updateSendBtn();

    document.addEventListener("click", function (e) {
      if (isOpen && !win.contains(e.target) && !fab.contains(e.target)) toggleChat();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isOpen) {
        if (renameOverlay.classList.contains("visible")) hideRenameModal();
        else if (modalOverlay.classList.contains("visible")) hideDeleteModal();
        else if (sidebarOpen) closeSidebar();
        else toggleChat();
      }
    });

    function formatTimeAgo(dateStr) {
      var date = new Date(dateStr); var now = new Date(); var diff = Math.floor((now - date) / 1000);
      if (diff < 60) return "À l'instant"; if (diff < 3600) return Math.floor(diff / 60) + " min";
      if (diff < 86400) return Math.floor(diff / 3600) + " h"; if (diff < 604800) return Math.floor(diff / 86400) + " j";
      return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
    }
    function escapeHtml(text) { var d = document.createElement("div"); d.textContent = text; return d.innerHTML; }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
