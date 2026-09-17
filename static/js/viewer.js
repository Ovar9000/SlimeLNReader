/**
 * AnyFlip / FlipHTML5 Local Viewer Engine (High Performance & Double-Page Spread)
 * That Time I Got Reincarnated as a Slime — Volume 22
 */

(function() {
  'use strict';

  // --- Constants & Global State ---
  const TOTAL_PAGES = 586;
  const BASE_PAGE_WIDTH = 595.32;
  const BASE_PAGE_HEIGHT = 841.92;
  const STORAGE_KEY_PAGE = 'tensura_v22_last_page';
  const STORAGE_KEY_BOOKMARKS = 'tensura_v22_bookmarks';
  const STORAGE_KEY_THEME = 'tensura_v22_theme';
  const STORAGE_KEY_SOUND = 'tensura_v22_sound';
  const STORAGE_KEY_MODE = 'tensura_v22_mode';
  const STORAGE_KEY_SPREAD = 'tensura_v22_spread';
  const STORAGE_KEY_RFS = 'tensura_v22_reader_fs';
  const STORAGE_KEY_RW = 'tensura_v22_reader_width';
  const STORAGE_KEY_RJP = 'tensura_v22_reader_jp';
  const STORAGE_KEY_RSERIF = 'tensura_v22_reader_serif';

  const TOC_DATA = [
    { title: "Prologue: Pure Malice (純粋な悪意)", page: 1 },
    { title: "Chapter 1: The Lord of Vice (悪徳の王)", page: 11 },
    { title: "Chapter 2: Time of Despair (絶望の時)", page: 167 },
    { title: "Chapter 3: The Apex's Showdown (頂上決戦)", page: 306 },
    { title: "Epilogue: Evil God Awakening (邪神覚醒)", page: 583 }
  ];

  let state = {
    currentPage: 1, // 1-based page number
    totalPages: TOTAL_PAGES,
    viewMode: 'reader', // 'reader' (reflowable, default) | 'flip' | 'scroll'
    spreadMode: 'double', // 'double' (original FlipHTML5 look) or 'single'
    zoomLevel: 1.0,
    panX: 0,
    panY: 0,
    isPanning: false,
    startPanX: 0,
    startPanY: 0,
    soundEnabled: true,
    autoFlip: false,
    autoFlipTimer: null,
    autoFlipInterval: 7500, // ms
    hasBackend: true,
    bookData: null,
    bookmarks: [],
    pdfDoc: null,
    // Reflowable reader typography prefs
    readerFS: 19,
    readerWidth: 680,
    readerShowJP: true,
    readerSerif: true
  };

  let pageFlipInstance = null;
  let audioCtx = null;
  let scrollObserver = null;
  let thumbObserver = null;

  // --- DOM Elements ---
  const DOM = {
    viewport: document.getElementById('app-viewport'),
    mainContainer: document.getElementById('main-container'),
    flipbookStage: document.getElementById('flipbook-stage'),
    flipbookWrapper: document.getElementById('flipbook-wrapper'),
    flipbook: document.getElementById('flipbook'),
    scrollStage: document.getElementById('scroll-stage'),
    scrollPagesList: document.getElementById('scroll-pages-list'),
    readerStage: document.getElementById('reader-stage'),
    readerScroll: document.getElementById('reader-scroll'),
    readerArticle: document.getElementById('reader-article'),
    readerBody: document.getElementById('reader-body'),
    readerChapterTitle: document.getElementById('reader-chapter-title'),
    readerChapterLabel: document.getElementById('reader-chapter-label'),
    readerPageNum: document.getElementById('reader-page-num'),
    readerProgressFill: document.getElementById('reader-progress-fill'),
    chapterDisplay: document.getElementById('current-chapter-display'),
    pageInput: document.getElementById('page-input'),
    totalPagesLabel: document.getElementById('total-pages-label'),
    pageSlider: document.getElementById('page-slider'),
    sliderTooltip: document.getElementById('slider-tooltip'),
    toast: document.getElementById('toast'),
    resumeBanner: document.getElementById('resume-banner'),
    resumePageNum: document.getElementById('resume-page-num'),
    bookEdgeLeft: document.getElementById('book-edge-left'),
    bookEdgeRight: document.getElementById('book-edge-right'),
    // Drawers
    tocDrawer: document.getElementById('toc-drawer'),
    tocList: document.getElementById('toc-list'),
    searchDrawer: document.getElementById('search-drawer'),
    searchInput: document.getElementById('search-input'),
    searchResults: document.getElementById('search-results-list'),
    searchCount: document.getElementById('search-count'),
    bookmarkDrawer: document.getElementById('bookmark-drawer'),
    bookmarkList: document.getElementById('bookmark-list'),
    themeDrawer: document.getElementById('theme-drawer'),
    thumbnailsDrawer: document.getElementById('thumbnails-drawer'),
    thumbScrollTrack: document.getElementById('thumb-scroll-track'),
    // Buttons
    btnModeReader: document.getElementById('btn-mode-reader'),
    btnModeFlip: document.getElementById('btn-mode-flip'),
    btnModeScroll: document.getElementById('btn-mode-scroll'),
    btnSidePrev: document.getElementById('btn-side-prev'),
    btnSideNext: document.getElementById('btn-side-next'),
    btnFirstPage: document.getElementById('btn-first-page'),
    btnPrevPage: document.getElementById('btn-prev-page'),
    btnNextPage: document.getElementById('btn-next-page'),
    btnLastPage: document.getElementById('btn-last-page'),
    btnSpreadToggle: document.getElementById('btn-spread-toggle'),
    btnZoomIn: document.getElementById('btn-zoom-in'),
    btnZoomOut: document.getElementById('btn-zoom-out'),
    btnZoomReset: document.getElementById('btn-zoom-reset'),
    btnAutoFlip: document.getElementById('btn-autoflip'),
    btnSound: document.getElementById('btn-sound'),
    btnTheme: document.getElementById('btn-theme'),
    btnFullscreen: document.getElementById('btn-fullscreen'),
    btnToc: document.getElementById('btn-toc'),
    btnThumbnails: document.getElementById('btn-thumbnails'),
    btnSearch: document.getElementById('btn-search'),
    btnBookmark: document.getElementById('btn-bookmark'),
    btnAddBookmark: document.getElementById('btn-add-bookmark'),
    btnResumeYes: document.getElementById('btn-resume-yes'),
    btnResumeDismiss: document.getElementById('btn-resume-dismiss')
  };

  // --- Initial Setup ---
  async function init() {
    loadPreferences();
    await checkBackend();
    await loadSearchData();
    buildTOC();
    buildThumbnails();
    initFlipbook();
    initScrollMode();
    initReader();
    bindEvents();
    applySpreadMode(false);
    checkResumeReading();

    // Activate saved (or default reader) mode cleanly, without toast spam on load
    setViewMode(state.viewMode, true);
    onPageChanged(state.currentPage);
  }

  // --- Persistence ---
  function loadPreferences() {
    // Read everything first (applying theme saves, so it must go last)
    const savedTheme = localStorage.getItem(STORAGE_KEY_THEME) || 'default';

    const savedSound = localStorage.getItem(STORAGE_KEY_SOUND);
    if (savedSound !== null) {
      state.soundEnabled = savedSound === 'true';
    }

    const savedBookmarks = localStorage.getItem(STORAGE_KEY_BOOKMARKS);
    if (savedBookmarks) {
      try { state.bookmarks = JSON.parse(savedBookmarks); } catch (e) { state.bookmarks = []; }
    }

    const savedMode = localStorage.getItem(STORAGE_KEY_MODE);
    if (savedMode && (savedMode === 'flip' || savedMode === 'scroll' || savedMode === 'reader')) {
      state.viewMode = savedMode;
    }

    const savedSpread = localStorage.getItem(STORAGE_KEY_SPREAD);
    if (savedSpread && (savedSpread === 'double' || savedSpread === 'single')) {
      state.spreadMode = savedSpread;
    }

    const savedFS = parseInt(localStorage.getItem(STORAGE_KEY_RFS), 10);
    if (savedFS >= 14 && savedFS <= 28) state.readerFS = savedFS;
    const savedW = parseInt(localStorage.getItem(STORAGE_KEY_RW), 10);
    if ([560, 680, 860].includes(savedW)) state.readerWidth = savedW;
    const savedJP = localStorage.getItem(STORAGE_KEY_RJP);
    if (savedJP !== null) state.readerShowJP = savedJP === 'true';
    const savedSerif = localStorage.getItem(STORAGE_KEY_RSERIF);
    if (savedSerif !== null) state.readerSerif = savedSerif === 'true';

    // Apply (these touch the DOM; setTheme saves, now with correct state)
    setTheme(savedTheme);
    updateSoundUI();
    renderBookmarks();
  }

  function savePreferences() {
    const themeMatch = document.body.className.match(/theme-(\w+)/);
    localStorage.setItem(STORAGE_KEY_THEME, themeMatch ? themeMatch[1] : 'default');
    localStorage.setItem(STORAGE_KEY_SOUND, state.soundEnabled);
    localStorage.setItem(STORAGE_KEY_BOOKMARKS, JSON.stringify(state.bookmarks));
    localStorage.setItem(STORAGE_KEY_MODE, state.viewMode);
    localStorage.setItem(STORAGE_KEY_SPREAD, state.spreadMode);
    localStorage.setItem(STORAGE_KEY_RFS, state.readerFS);
    localStorage.setItem(STORAGE_KEY_RW, state.readerWidth);
    localStorage.setItem(STORAGE_KEY_RJP, state.readerShowJP);
    localStorage.setItem(STORAGE_KEY_RSERIF, state.readerSerif);
  }

  function saveLastPage(page) {
    if (page >= 1 && page <= TOTAL_PAGES) {
      localStorage.setItem(STORAGE_KEY_PAGE, page);
    }
  }

  function checkResumeReading() {
    const lastPage = parseInt(localStorage.getItem(STORAGE_KEY_PAGE), 10);
    if (lastPage && lastPage > 2 && lastPage <= TOTAL_PAGES) {
      DOM.resumePageNum.textContent = lastPage;
      DOM.resumeBanner.style.display = 'flex';
    }
  }

  // --- Backend Check & PDF.js Fallback ---
  async function checkBackend() {
    try {
      const res = await fetch('/api/status', { method: 'GET', cache: 'no-cache' });
      if (res.ok) {
        state.hasBackend = true;
        console.log('Using PyMuPDF high-speed backend server.');
        return;
      }
    } catch (e) {
      state.hasBackend = false;
    }

    console.warn('Backend server not detected. Initializing client-side PDF.js fallback...');
    state.hasBackend = false;
    if (window.pdfjsLib) {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'static/js/pdf.worker.min.js';
      try {
        state.pdfDoc = await window.pdfjsLib.getDocument('Volume_22_MTL.pdf').promise;
        console.log('PDF.js initialized successfully.');
      } catch (err) {
        console.error('Failed to load PDF with PDF.js:', err);
      }
    }
  }

  // --- Fetch Search & Book Metadata ---
  async function loadSearchData() {
    try {
      const res = await fetch('static/book_data.json');
      if (res.ok) {
        state.bookData = await res.json();
      }
    } catch (e) {
      console.log('Search data will be queried via backend API.');
    }
  }

  // --- Procedural Sound Effects (Web Audio API) ---
  function playPageFlipSound() {
    if (!state.soundEnabled) return;
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }

      const duration = 0.28;
      const bufferSize = Math.floor(audioCtx.sampleRate * duration);
      const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
      const data = buffer.getChannelData(0);

      // Pink noise synthesis for realistic crisp paper friction
      let b0 = 0, b1 = 0, b2 = 0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        b0 = 0.99 * b0 + white * 0.05;
        b1 = 0.96 * b1 + white * 0.11;
        b2 = 0.86 * b2 + white * 0.25;
        data[i] = (b0 + b1 + b2 + white * 0.1) * 0.35;
      }

      const noise = audioCtx.createBufferSource();
      noise.buffer = buffer;

      const filter = audioCtx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(800, audioCtx.currentTime);
      filter.frequency.exponentialRampToValueAtTime(3400, audioCtx.currentTime + 0.1);
      filter.frequency.exponentialRampToValueAtTime(450, audioCtx.currentTime + duration);

      const gain = audioCtx.createGain();
      gain.gain.setValueAtTime(0.01, audioCtx.currentTime);
      gain.gain.linearRampToValueAtTime(0.35, audioCtx.currentTime + 0.07);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);

      noise.connect(filter);
      filter.connect(gain);
      gain.connect(audioCtx.destination);

      noise.start();
    } catch (e) {
      // Ignore audio policy issues
    }
  }

  // --- Page Image URL Provider (sharper default for tiny novel text) ---
  function getPageImageUrl(pageNum, dpi = 180) {
    if (state.hasBackend) {
      return `/api/page/${pageNum}?dpi=${dpi}`;
    }
    return null;
  }

  function getThumbnailUrl(pageNum) {
    if (state.hasBackend) {
      return `/api/thumbnail/${pageNum}`;
    }
    return null;
  }

  // --- Dimensions Calculation (Maximizing Readable Area) ---
  function calculateFlipbookDimensions() {
    const containerW = DOM.mainContainer.clientWidth || window.innerWidth;
    const containerH = DOM.mainContainer.clientHeight || (window.innerHeight - 94);
    const aspect = BASE_PAGE_WIDTH / BASE_PAGE_HEIGHT; // ~0.7071

    const isSingle = (state.spreadMode === 'single') || (containerW < 768);

    if (isSingle) {
      let h = Math.round(containerH * 0.96);
      let w = Math.round(h * aspect);
      if (w > containerW * 0.94) {
        w = Math.round(containerW * 0.94);
        h = Math.round(w / aspect);
      }
      return { width: w, height: h, isSingle: true };
    } else {
      // 2-Page Double Spread
      let h = Math.round(containerH * 0.96);
      let w = Math.round(h * aspect);

      // Total width is 2 * w
      if (w * 2 > containerW * 0.95) {
        w = Math.round((containerW * 0.95) / 2);
        h = Math.round(w / aspect);
      }
      return { width: w, height: h, isSingle: false };
    }
  }

  // --- 1. Flipbook Mode (StPageFlip) ---
  function initFlipbook() {
    DOM.flipbook.innerHTML = '';

    // Create 586 page elements
    for (let i = 1; i <= TOTAL_PAGES; i++) {
      const pageDiv = document.createElement('div');
      pageDiv.className = 'page';
      pageDiv.id = `page-${i}`;
      pageDiv.setAttribute('data-page', i);
      pageDiv.setAttribute('data-density', 'soft');

      const content = document.createElement('div');
      content.className = 'page-content';
      content.id = `page-content-${i}`;
      content.innerHTML = `
        <div class="page-loading" id="page-loading-${i}">
          <div class="page-loading-spinner"></div>
          <span style="font-size:12px; font-weight:600;">Page ${i}</span>
        </div>
      `;

      // Corner curl hint
      const corner = document.createElement('div');
      corner.className = `corner-hint ${i % 2 !== 0 ? 'corner-hint-left' : 'corner-hint-right'}`;
      corner.title = i % 2 !== 0 ? 'Click or drag to flip left' : 'Click or drag to flip right';

      pageDiv.appendChild(content);
      pageDiv.appendChild(corner);
      DOM.flipbook.appendChild(pageDiv);
    }

    const dims = calculateFlipbookDimensions();

    try {
      pageFlipInstance = new St.PageFlip(DOM.flipbook, {
        width: dims.width,
        height: dims.height,
        size: 'stretch',
        minWidth: 320,
        maxWidth: 1600,
        minHeight: 450,
        maxHeight: 2000,
        maxShadowOpacity: 0.5,
        showCover: false, // Double paged from start! Page 1 on left, Page 2 on right!
        usePortrait: dims.isSingle,
        startPage: 0, // Spread [0, 1] -> Pages 1 and 2
        drawShadow: true,
        flippingTime: 550,
        useMouseEvents: true,
        swipeDistance: 20,
        showPageCorners: true
      });

      pageFlipInstance.loadFromHTML(document.querySelectorAll('.page'));

      // Event: Flip completed
      pageFlipInstance.on('flip', (e) => {
        const pageIdx = e.data; // 0-based
        const pageNum = pageIdx + 1;
        onPageChanged(pageNum);
        playPageFlipSound();
      });

      // Event: Change State (preload adjacent pages on fold)
      pageFlipInstance.on('changeState', (e) => {
        if (e.data === 'user_fold' || e.data === 'fold_corner') {
          const cur = pageFlipInstance.getCurrentPageIndex() + 1;
          updateVirtualWindow(cur);
        }
      });

      // Event: Change orientation
      pageFlipInstance.on('changeOrientation', (e) => {
        updateBookEdgeStack(state.currentPage);
      });

      // Initial render window
      updateVirtualWindow(state.currentPage);
      updateUI();
    } catch (err) {
      console.error('Error initializing StPageFlip:', err);
      showToast('Error initializing 3D flipbook engine.');
    }
  }

  // --- Virtual Window Page Loader ---
  function updateVirtualWindow(targetPage) {
    const range = 6;
    const minPage = Math.max(1, targetPage - range);
    const maxPage = Math.min(TOTAL_PAGES, targetPage + range + 1);

    // Load active range
    for (let p = minPage; p <= maxPage; p++) {
      loadPageContent(p);
    }

    // Unload pages outside range to keep memory minimal (<50MB)
    for (let p = 1; p <= TOTAL_PAGES; p++) {
      if (p < minPage - 3 || p > maxPage + 3) {
        unloadPageContent(p);
      }
    }
  }

  function loadPageContent(pageNum) {
    const contentDiv = document.getElementById(`page-content-${pageNum}`);
    if (!contentDiv) return;

    if (contentDiv.querySelector('img') || contentDiv.querySelector('canvas')) {
      return;
    }

    if (state.hasBackend) {
      const img = new Image();
      img.decoding = 'async';
      img.alt = `Page ${pageNum}`;
      img.src = getPageImageUrl(pageNum, 180);
      img.onload = () => {
        contentDiv.innerHTML = '';
        contentDiv.appendChild(img);
      };
      img.onerror = () => {
        if (state.pdfDoc) renderPageWithPdfJs(pageNum, contentDiv);
      };
    } else if (state.pdfDoc) {
      renderPageWithPdfJs(pageNum, contentDiv);
    }
  }

  function unloadPageContent(pageNum) {
    const contentDiv = document.getElementById(`page-content-${pageNum}`);
    if (!contentDiv) return;
    if (contentDiv.querySelector('img') || contentDiv.querySelector('canvas')) {
      contentDiv.innerHTML = `
        <div class="page-loading" id="page-loading-${pageNum}">
          <div class="page-loading-spinner"></div>
          <span style="font-size:12px; font-weight:600;">Page ${pageNum}</span>
        </div>
      `;
    }
  }

  async function renderPageWithPdfJs(pageNum, container) {
    try {
      const page = await state.pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: 1.6 });
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = viewport.width;
      canvas.height = viewport.height;

      const renderCtx = { canvasContext: ctx, viewport: viewport };
      await page.render(renderCtx).promise;

      container.innerHTML = '';
      container.appendChild(canvas);
    } catch (e) {
      console.error(`PDF.js render error for page ${pageNum}:`, e);
    }
  }

  // --- 2. Continuous Vertical Scroll Mode ---
  function initScrollMode() {
    DOM.scrollPagesList.innerHTML = '';

    for (let i = 1; i <= TOTAL_PAGES; i++) {
      const item = document.createElement('div');
      item.className = 'scroll-page-item';
      item.id = `scroll-item-${i}`;
      item.setAttribute('data-page', i);
      item.innerHTML = `
        <div class="page-loading">
          <div class="page-loading-spinner"></div>
          <span>Page ${i}</span>
        </div>
        <div class="scroll-page-num">${i}</div>
      `;
      DOM.scrollPagesList.appendChild(item);
    }

    if ('IntersectionObserver' in window) {
      scrollObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          const pageNum = parseInt(entry.target.getAttribute('data-page'), 10);
          if (entry.isIntersecting) {
            loadScrollPageImage(pageNum, entry.target);
            if (state.viewMode === 'scroll') {
              state.currentPage = pageNum;
              updateUI(false);
            }
          } else {
            if (Math.abs(state.currentPage - pageNum) > 6) {
              unloadScrollPageImage(pageNum, entry.target);
            }
          }
        });
      }, { root: DOM.scrollStage, rootMargin: '600px 0px 600px 0px' });

      document.querySelectorAll('.scroll-page-item').forEach(el => scrollObserver.observe(el));
    }
  }

  function loadScrollPageImage(pageNum, targetEl) {
    if (targetEl.querySelector('img')) return;

    const img = new Image();
    img.decoding = 'async';
    img.alt = `Page ${pageNum}`;
    img.src = getPageImageUrl(pageNum, 180);
    img.onload = () => {
      const loading = targetEl.querySelector('.page-loading');
      if (loading) loading.remove();
      targetEl.prepend(img);
    };
  }

  function unloadScrollPageImage(pageNum, targetEl) {
    const img = targetEl.querySelector('img');
    if (img) {
      img.remove();
      if (!targetEl.querySelector('.page-loading')) {
        const loading = document.createElement('div');
        loading.className = 'page-loading';
        loading.innerHTML = `<div class="page-loading-spinner"></div><span>Page ${pageNum}</span>`;
        targetEl.prepend(loading);
      }
    }
  }

  // --- 3. Reflowable Text Reader Mode (the actual fix for "it's a PDF") ---
  // Renders extracted bilingual text as large, selectable, reflowable
  // typography instead of tiny fixed scan images.
  const JP_RE = /[\u3040-\u30ff\u4e00-\u9faf\uff00-\uffef]/;
  const HEADING_RE = /^(volume\s+\d+|prologue|chapter\s+\d*|epilogue|illustration|table of contents|character intro)/i;

  function initReader() {
    applyReaderPrefs(false);
    renderReaderPage(state.currentPage);
  }

  function applyReaderPrefs(notify = true) {
    if (!DOM.readerArticle) return;
    DOM.readerArticle.style.setProperty('--reader-fs', state.readerFS + 'px');
    DOM.readerArticle.style.setProperty('--reader-maxw', state.readerWidth + 'px');
    DOM.readerBody.classList.toggle('hide-jp', !state.readerShowJP);
    DOM.readerArticle.classList.toggle('font-sans', !state.readerSerif);

    const jpBtn = document.getElementById('btn-jp-toggle');
    if (jpBtn) jpBtn.classList.toggle('active', state.readerShowJP);
    const serifBtn = document.getElementById('btn-serif-toggle');
    if (serifBtn) serifBtn.classList.toggle('active', state.readerSerif);
    ['narrow', 'wide', 'full'].forEach(() => {});
    const wN = document.getElementById('btn-width-narrow');
    const wW = document.getElementById('btn-width-wide');
    const wF = document.getElementById('btn-width-full');
    if (wN) wN.classList.toggle('active', state.readerWidth === 560);
    if (wW) wW.classList.toggle('active', state.readerWidth === 680);
    if (wF) wF.classList.toggle('active', state.readerWidth === 860);

    if (notify !== false) savePreferences();
  }

  function getReaderText(pageNum) {
    if (state.bookData && state.bookData.pages && state.bookData.pages[pageNum - 1]) {
      return state.bookData.pages[pageNum - 1];
    }
    return null;
  }

  function renderReaderPage(pageNum) {
    if (!DOM.readerBody) return;
    const raw = getReaderText(pageNum);

    // Chapter label
    let curChapter = TOC_DATA[0].title;
    for (let c of TOC_DATA) {
      if (pageNum >= c.page) curChapter = c.title;
    }
    if (DOM.readerChapterLabel) DOM.readerChapterLabel.textContent = curChapter;
    if (DOM.readerChapterTitle) DOM.readerChapterTitle.textContent = curChapter.split('(')[0].trim();
    if (DOM.readerPageNum) DOM.readerPageNum.textContent = pageNum;
    if (DOM.readerProgressFill) {
      DOM.readerProgressFill.style.width = `${Math.round((pageNum / TOTAL_PAGES) * 100)}%`;
    }

    if (!raw || !raw.trim()) {
      // No extracted text (likely an illustration page) — guide user to PDF scan
      DOM.readerBody.innerHTML = `
        <div class="reader-empty">
          This page appears to be an illustration with no extractable text.<br>
          <button class="reader-nav-btn" id="btn-view-scan" style="margin-top:14px;">View original scan →</button>
        </div>`;
      const scanBtn = document.getElementById('btn-view-scan');
      if (scanBtn) scanBtn.onclick = () => setViewMode('flip');
      return;
    }

    const lines = raw.split('\n');
    const html = [];
    let headingUsed = 0;

    for (let rawLine of lines) {
      const line = rawLine.trim();
      if (!line) {
        html.push('<div class="rl-spacer"></div>');
        continue;
      }
      const isJP = JP_RE.test(line);
      const cls = isJP ? 'rl-jp' : 'rl-en';

      // First 1-2 meaningful EN lines that look like titles become headings
      if (!isJP && headingUsed < 2 && line.length < 90 && HEADING_RE.test(line)) {
        html.push(`<div class="rl-heading">${escapeHtml(line)}</div>`);
        headingUsed++;
        continue;
      }

      const isDialogue = /^[“"'\u300e\u300c『「]/.test(line);
      html.push(`<p class="${cls}${isDialogue && !isJP ? ' rl-dialogue' : ''}">${escapeHtml(line)}</p>`);
    }

    DOM.readerBody.innerHTML = html.join('');
    DOM.readerBody.classList.toggle('hide-jp', !state.readerShowJP);
  }

  // --- Page Flip Navigation Logic ---
  function goToPage(pageNum, triggerFlip = true) {
    pageNum = Math.max(1, Math.min(TOTAL_PAGES, pageNum));
    state.currentPage = pageNum;

    if (state.viewMode === 'flip' && pageFlipInstance) {
      const targetIdx = pageNum - 1;
      if (triggerFlip) {
        pageFlipInstance.flip(targetIdx);
      } else {
        pageFlipInstance.turnToPage(targetIdx);
      }
    } else if (state.viewMode === 'scroll') {
      const targetEl = document.getElementById(`scroll-item-${pageNum}`);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } else if (state.viewMode === 'reader') {
      renderReaderPage(pageNum);
      if (DOM.readerScroll) DOM.readerScroll.scrollTo({ top: 0, behavior: triggerFlip ? 'smooth' : 'auto' });
    }

    onPageChanged(pageNum);
  }

  function readerStep(delta) {
    goToPage(state.currentPage + delta, false);
    if (DOM.readerScroll) DOM.readerScroll.scrollTo({ top: 0, behavior: 'auto' });
  }

  function onPageChanged(pageNum) {
    state.currentPage = pageNum;
    updateVirtualWindow(pageNum);
    if (state.viewMode === 'reader') {
      // Re-render in case the event came from slider / TOC / search / keyboard
      const bodyFirst = DOM.readerBody ? DOM.readerBody.getAttribute('data-pg') : null;
      if (String(bodyFirst) !== String(pageNum)) {
        renderReaderPage(pageNum);
      }
      if (DOM.readerBody) DOM.readerBody.setAttribute('data-pg', pageNum);
      if (DOM.readerPageNum) DOM.readerPageNum.textContent = pageNum;
      if (DOM.readerProgressFill) {
        DOM.readerProgressFill.style.width = `${Math.round((pageNum / TOTAL_PAGES) * 100)}%`;
      }
      let curChapter = TOC_DATA[0].title;
      for (let c of TOC_DATA) {
        if (pageNum >= c.page) curChapter = c.title;
      }
      if (DOM.readerChapterLabel) DOM.readerChapterLabel.textContent = curChapter;
      if (DOM.readerChapterTitle) DOM.readerChapterTitle.textContent = curChapter.split('(')[0].trim();
    }
    updateUI();
    saveLastPage(pageNum);
    updateBookEdgeStack(pageNum);
  }

  function updateBookEdgeStack(pageNum) {
    const ratio = pageNum / TOTAL_PAGES;
    const leftThickness = Math.max(2, Math.round(ratio * 16));
    const rightThickness = Math.max(2, Math.round((1 - ratio) * 16));

    if (DOM.bookEdgeLeft) DOM.bookEdgeLeft.style.width = `${leftThickness}px`;
    if (DOM.bookEdgeRight) DOM.bookEdgeRight.style.width = `${rightThickness}px`;
  }

  // --- UI Update Coordinator ---
  function updateUI(syncInputs = true) {
    const cur = state.currentPage;

    // 1. Update Chapter Subtitle
    let curChapter = TOC_DATA[0].title;
    for (let c of TOC_DATA) {
      if (cur >= c.page) curChapter = c.title;
    }
    DOM.chapterDisplay.textContent = curChapter;

    // 2. Update Input & Slider (Show 2-page range if in double spread)
    if (syncInputs) {
      let displayStr = `${cur}`;
      if (state.viewMode === 'flip' && state.spreadMode === 'double' && window.innerWidth >= 768) {
        const other = cur % 2 !== 0 ? cur + 1 : cur - 1;
        const low = Math.min(cur, other);
        const high = Math.min(TOTAL_PAGES, Math.max(cur, other));
        displayStr = low === high ? `${low}` : `${low}-${high}`;
      }
      DOM.pageInput.value = displayStr;
      DOM.pageSlider.value = cur;
    }

    // 3. Highlight TOC item
    document.querySelectorAll('.toc-item').forEach(el => {
      el.classList.toggle('active', el.getAttribute('data-title') === curChapter);
    });

    // 4. Highlight Thumbnail
    document.querySelectorAll('.thumb-card').forEach(el => {
      const p = parseInt(el.getAttribute('data-page'), 10);
      const isCur = (p === cur) || (state.viewMode === 'flip' && state.spreadMode === 'double' && (p === cur + 1 || p === cur - 1));
      el.classList.toggle('active', isCur);
    });

    // 5. Update Bookmark Button State
    const isBookmarked = state.bookmarks.some(b => b.page === cur);
    DOM.btnBookmark.classList.toggle('active', isBookmarked);
  }

  // --- Table of Contents ---
  function buildTOC() {
    DOM.tocList.innerHTML = '';
    TOC_DATA.forEach(chap => {
      const li = document.createElement('li');
      li.className = 'toc-item';
      li.setAttribute('data-page', chap.page);
      li.setAttribute('data-title', chap.title);
      li.innerHTML = `
        <span style="font-size:13px; font-weight:500;">${chap.title}</span>
        <span class="toc-page-badge">p. ${chap.page}</span>
      `;
      li.onclick = () => {
        goToPage(chap.page);
        closeAllDrawers();
        showToast(`Jumped to ${chap.title}`);
      };
      DOM.tocList.appendChild(li);
    });
  }

  // --- Thumbnails Tray Drawer ---
  function buildThumbnails() {
    DOM.thumbScrollTrack.innerHTML = '';
    for (let i = 1; i <= TOTAL_PAGES; i++) {
      const card = document.createElement('div');
      card.className = 'thumb-card';
      card.setAttribute('data-page', i);
      card.id = `thumb-card-${i}`;
      card.innerHTML = `<div class="thumb-page-label">${i}</div>`;
      card.onclick = () => {
        goToPage(i);
        closeAllDrawers();
      };
      DOM.thumbScrollTrack.appendChild(card);
    }

    if ('IntersectionObserver' in window) {
      thumbObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const pageNum = parseInt(entry.target.getAttribute('data-page'), 10);
            loadThumbnailImage(pageNum, entry.target);
            thumbObserver.unobserve(entry.target);
          }
        });
      }, { root: DOM.thumbnailsDrawer, rootMargin: '250px' });

      document.querySelectorAll('.thumb-card').forEach(el => thumbObserver.observe(el));
    }
  }

  function loadThumbnailImage(pageNum, cardEl) {
    if (cardEl.querySelector('img')) return;
    const img = new Image();
    img.decoding = 'async';
    img.alt = `Page ${pageNum}`;
    img.src = getThumbnailUrl(pageNum);
    img.onload = () => {
      cardEl.prepend(img);
    };
  }

  // --- Full-Text Search ---
  let searchDebounce = null;
  function handleSearchInput(e) {
    clearTimeout(searchDebounce);
    const query = e.target.value.trim().toLowerCase();
    if (!query) {
      DOM.searchResults.innerHTML = `
        <div style="text-align:center; padding:30px 10px; color:var(--text-muted); font-size:13px;">
          Type a word or character name to search across all 586 pages.
        </div>
      `;
      DOM.searchCount.textContent = '';
      return;
    }

    searchDebounce = setTimeout(() => {
      performSearch(query);
    }, 250);
  }

  async function performSearch(query) {
    DOM.searchResults.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-dim);">Searching...</div>';

    if (state.bookData && state.bookData.pages) {
      const results = [];
      const pages = state.bookData.pages;
      for (let i = 0; i < pages.length; i++) {
        const text = pages[i];
        const lower = text.toLowerCase();
        const idx = lower.indexOf(query);
        if (idx !== -1) {
          const start = Math.max(0, idx - 45);
          const end = Math.min(text.length, idx + query.length + 65);
          let snippet = text.substring(start, end).replace(/\n/g, ' ').trim();
          if (start > 0) snippet = '...' + snippet;
          if (end < text.length) snippet = snippet + '...';

          let chap = TOC_DATA[0].title;
          const pageNum = i + 1;
          for (let c of TOC_DATA) {
            if (pageNum >= c.page) chap = c.title;
          }

          results.push({ page: pageNum, snippet: snippet, chapter: chap });
          if (results.length >= 60) break;
        }
      }
      renderSearchResults(query, results);
      return;
    }

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      if (res.ok) {
        const data = await res.json();
        renderSearchResults(query, data.results || []);
      }
    } catch (e) {
      DOM.searchResults.innerHTML = '<div style="text-align:center; padding:20px; color:#ef4444;">Search failed.</div>';
    }
  }

  function renderSearchResults(query, results) {
    DOM.searchCount.textContent = `${results.length} matches`;
    if (results.length === 0) {
      DOM.searchResults.innerHTML = `
        <div style="text-align:center; padding:30px 10px; color:var(--text-muted); font-size:13px;">
          No occurrences found for "<strong>${escapeHtml(query)}</strong>".
        </div>
      `;
      return;
    }

    DOM.searchResults.innerHTML = '';
    results.forEach(res => {
      const div = document.createElement('div');
      div.className = 'search-result-item';

      const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
      const highlightedSnippet = escapeHtml(res.snippet).replace(regex, '<mark>$1</mark>');

      div.innerHTML = `
        <div class="search-result-header">
          <span class="search-result-page">Page ${res.page}</span>
          <span class="search-result-chapter">${escapeHtml(res.chapter)}</span>
        </div>
        <div class="search-result-snippet">${highlightedSnippet}</div>
      `;

      div.onclick = () => {
        goToPage(res.page);
        closeAllDrawers();
        showToast(`Jumped to Page ${res.page}`);
      };

      DOM.searchResults.appendChild(div);
    });
  }

  // --- Bookmarks Logic ---
  function toggleCurrentBookmark() {
    const cur = state.currentPage;
    const existingIndex = state.bookmarks.findIndex(b => b.page === cur);

    if (existingIndex >= 0) {
      state.bookmarks.splice(existingIndex, 1);
      showToast(`Removed Bookmark on Page ${cur}`);
    } else {
      let chap = TOC_DATA[0].title;
      for (let c of TOC_DATA) {
        if (cur >= c.page) chap = c.title;
      }
      state.bookmarks.push({
        page: cur,
        chapter: chap,
        timestamp: new Date().toLocaleDateString()
      });
      showToast(`Bookmarked Page ${cur}`);
    }

    state.bookmarks.sort((a, b) => a.page - b.page);
    savePreferences();
    renderBookmarks();
    updateUI();
  }

  function renderBookmarks() {
    DOM.bookmarkList.innerHTML = '';
    if (state.bookmarks.length === 0) {
      DOM.bookmarkList.innerHTML = `
        <div style="text-align:center; padding:30px 10px; color:var(--text-muted); font-size:13px;">
          No bookmarks yet.<br>Click "Bookmark Current Page" while reading!
        </div>
      `;
      return;
    }

    state.bookmarks.forEach((bm, idx) => {
      const div = document.createElement('div');
      div.className = 'bookmark-item';
      div.innerHTML = `
        <div>
          <div style="font-size:13px; font-weight:700; color:var(--primary);">Page ${bm.page}</div>
          <div style="font-size:11px; color:var(--text-muted);">${escapeHtml(bm.chapter)} · ${bm.timestamp}</div>
        </div>
        <button class="bookmark-del-btn" title="Delete bookmark">✕</button>
      `;

      div.onclick = (e) => {
        if (e.target.classList.contains('bookmark-del-btn')) {
          e.stopPropagation();
          state.bookmarks.splice(idx, 1);
          savePreferences();
          renderBookmarks();
          updateUI();
          return;
        }
        goToPage(bm.page);
        closeAllDrawers();
        showToast(`Jumped to Bookmark (Page ${bm.page})`);
      };

      DOM.bookmarkList.appendChild(div);
    });
  }

  // --- Zoom & Pan Logic ---
  function setZoom(zoom) {
    state.zoomLevel = Math.max(0.8, Math.min(2.5, zoom));
    if (state.zoomLevel === 1.0) {
      state.panX = 0;
      state.panY = 0;
    }
    applyTransform();
    DOM.flipbookStage.classList.toggle('is-zoomed', state.zoomLevel > 1.0);
    showToast(`Zoom: ${Math.round(state.zoomLevel * 100)}%`);
  }

  function resetZoom() {
    state.zoomLevel = 1.0;
    state.panX = 0;
    state.panY = 0;
    applyTransform();
    DOM.flipbookStage.classList.remove('is-zoomed');
    showToast('Zoom Reset');
  }

  function applyTransform() {
    DOM.flipbookStage.style.transform = `scale(${state.zoomLevel}) translate(${state.panX}px, ${state.panY}px)`;
  }

  // --- Spread Size Layout (explicit px sizing) ---
  // StPageFlip in "stretch" mode measures its own element to compute page
  // size. Left to CSS shrink-to-fit it collapses to its min-width floor
  // (tiny floating book). Pinning exact pixel dimensions makes the book
  // fill the viewport deterministically and keeps update() idempotent.
  function layoutFlipbook() {
    if (!pageFlipInstance) return;
    try {
      const dims = calculateFlipbookDimensions();
      const totalW = dims.isSingle ? dims.width : dims.width * 2;
      try { pageFlipInstance.getSettings().usePortrait = dims.isSingle; } catch (e) {}
      DOM.flipbook.style.width = `${totalW}px`;
      DOM.flipbook.style.height = `${dims.height}px`;
      // Override the min-width/height floor PageFlip set at construction
      // (it bakes in the construction-time spread), so the block measures
      // exactly our dimensions instead of a stale floor.
      DOM.flipbook.style.minWidth = `${totalW}px`;
      DOM.flipbook.style.minHeight = `${dims.height}px`;
      pageFlipInstance.update();
    } catch (e) {}
  }

  // --- Spread Mode (Single vs Double Page) ---
  function applySpreadMode(notify = true) {
    const isSingle = state.spreadMode === 'single';
    DOM.btnSpreadToggle.classList.toggle('active', isSingle);
    DOM.btnSpreadToggle.setAttribute('data-tooltip', isSingle ? 'Current: 1-Page (Click for 2-Page)' : 'Current: 2-Page Spread (Click for 1-Page)');

    layoutFlipbook();

    if (notify) showToast(isSingle ? 'Single Page Mode' : 'Double Page Spread Mode');
    savePreferences();
    updateUI();
  }

  function toggleSpreadMode() {
    state.spreadMode = state.spreadMode === 'double' ? 'single' : 'double';
    applySpreadMode(true);
  }

  // --- Auto-Flip (Slideshow) Mode ---
  function toggleAutoFlip() {
    state.autoFlip = !state.autoFlip;
    DOM.btnAutoFlip.classList.toggle('active', state.autoFlip);

    if (state.autoFlip) {
      showToast('Auto-Play Started (7.5s/spread)');
      DOM.btnAutoFlip.innerHTML = `
        <svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
      `;
      startAutoFlipTimer();
    } else {
      showToast('Auto-Play Paused');
      DOM.btnAutoFlip.innerHTML = `
        <svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
      `;
      clearInterval(state.autoFlipTimer);
    }
  }

  function startAutoFlipTimer() {
    clearInterval(state.autoFlipTimer);
    state.autoFlipTimer = setInterval(() => {
      if (state.currentPage >= TOTAL_PAGES) {
        toggleAutoFlip();
        return;
      }
      if (state.viewMode === 'flip' && pageFlipInstance) {
        pageFlipInstance.flipNext();
      } else {
        goToPage(state.currentPage + 1);
      }
    }, state.autoFlipInterval);
  }

  // --- Theme Switching (preserves mode class) ---
  function setTheme(theme) {
    document.body.classList.remove('theme-wood', 'theme-oled', 'theme-light', 'theme-default');
    if (theme && theme !== 'default') {
      document.body.classList.add(`theme-${theme}`);
    }
    document.querySelectorAll('.theme-card').forEach(card => {
      card.classList.toggle('active', card.getAttribute('data-theme') === theme);
    });
    savePreferences();
  }

  // --- Drawers Management ---
  function toggleDrawer(drawerEl) {
    const isOpen = drawerEl.classList.contains('open');
    closeAllDrawers();
    if (!isOpen) {
      drawerEl.classList.add('open');
      if (drawerEl === DOM.searchDrawer) {
        DOM.searchInput.focus();
      } else if (drawerEl === DOM.thumbnailsDrawer) {
        const card = document.getElementById(`thumb-card-${state.currentPage}`);
        if (card) card.scrollIntoView({ behavior: 'smooth', inline: 'center' });
      }
    }
  }

  function closeAllDrawers() {
    document.querySelectorAll('.drawer-panel, #thumbnails-drawer').forEach(el => el.classList.remove('open'));
  }

  // --- Fullscreen Toggle ---
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }

  // --- Toast Notification ---
  let toastTimer = null;
  function showToast(msg) {
    DOM.toast.textContent = msg;
    DOM.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      DOM.toast.classList.remove('show');
    }, 1800);
  }

  // --- Sound Toggle UI ---
  function updateSoundUI() {
    DOM.btnSound.classList.toggle('active', state.soundEnabled);
    DOM.btnSound.setAttribute('data-tooltip', state.soundEnabled ? 'Page Turn Sound: ON' : 'Page Turn Sound: MUTED');
    DOM.btnSound.innerHTML = state.soundEnabled
      ? `<svg viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`
      : `<svg viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>`;
  }

  // --- Reading Mode Toggle (Reader / Flip / Scroll) ---
  function setViewMode(mode, silent = false) {
    state.viewMode = mode;
    savePreferences();

    if (DOM.btnModeReader) DOM.btnModeReader.classList.toggle('active', mode === 'reader');
    DOM.btnModeFlip.classList.toggle('active', mode === 'flip');
    DOM.btnModeScroll.classList.toggle('active', mode === 'scroll');

    document.body.classList.toggle('mode-reader', mode === 'reader');

    const show = (el, on) => {
      if (!el) return;
      el.classList.toggle('stage-active', on);
      el.classList.toggle('stage-inactive', !on);
    };
    show(DOM.readerStage, mode === 'reader');
    show(DOM.flipbookStage, mode === 'flip');
    show(DOM.scrollStage, mode === 'scroll');

    const inReader = mode === 'reader';
    const inFlip = mode === 'flip';
    if (DOM.btnSidePrev) DOM.btnSidePrev.style.display = inFlip ? 'flex' : 'flex';
    if (DOM.btnSideNext) DOM.btnSideNext.style.display = inFlip ? 'flex' : 'flex';
    if (DOM.btnSpreadToggle) DOM.btnSpreadToggle.style.display = inFlip ? 'flex' : 'none';

    if (mode === 'flip') {
      // Update flipbook layout and jump cleanly
      requestAnimationFrame(() => {
        if (pageFlipInstance) {
          try {
            layoutFlipbook();
            pageFlipInstance.turnToPage(state.currentPage - 1);
          } catch(e) {
            console.warn('pageFlip update on mode switch:', e);
          }
          updateVirtualWindow(state.currentPage);
          updateUI();
        }
      });
      if (!silent) showToast('Flipbook: original PDF scans (use Reader for large text)');
    } else if (mode === 'scroll') {
      requestAnimationFrame(() => {
        const item = document.getElementById(`scroll-item-${state.currentPage}`);
        if (item) {
          item.scrollIntoView({ behavior: 'auto', block: 'start' });
        }
      });
      if (!silent) showToast('Scroll: original PDF scans (use Reader for large text)');
    } else {
      requestAnimationFrame(() => {
        renderReaderPage(state.currentPage);
        if (DOM.readerScroll) DOM.readerScroll.scrollTo({ top: 0, behavior: 'auto' });
        updateUI();
      });
      if (!silent) showToast('Reader Mode: large reflowable text');
    }
  }

  // --- Bind Event Listeners ---
  function bindEvents() {
    if (DOM.btnModeReader) DOM.btnModeReader.onclick = () => setViewMode('reader');
    DOM.btnModeFlip.onclick = () => setViewMode('flip');
    DOM.btnModeScroll.onclick = () => setViewMode('scroll');

    const stepPrev = () => {
      if (state.viewMode === 'flip' && pageFlipInstance) pageFlipInstance.flipPrev();
      else readerStep(-1);
    };
    const stepNext = () => {
      if (state.viewMode === 'flip' && pageFlipInstance) pageFlipInstance.flipNext();
      else readerStep(1);
    };

    DOM.btnSidePrev.onclick = stepPrev;
    DOM.btnSideNext.onclick = stepNext;
    DOM.btnPrevPage.onclick = stepPrev;
    DOM.btnNextPage.onclick = stepNext;
    DOM.btnFirstPage.onclick = () => goToPage(1);
    DOM.btnLastPage.onclick = () => goToPage(TOTAL_PAGES);

    const rPrev = document.getElementById('btn-reader-prev');
    const rNext = document.getElementById('btn-reader-next');
    if (rPrev) rPrev.onclick = () => readerStep(-1);
    if (rNext) rNext.onclick = () => readerStep(1);

    // Reader typography controls
    const fInc = document.getElementById('btn-font-inc');
    const fDec = document.getElementById('btn-font-dec');
    if (fInc) fInc.onclick = () => {
      state.readerFS = Math.min(28, state.readerFS + 1);
      applyReaderPrefs();
    };
    if (fDec) fDec.onclick = () => {
      state.readerFS = Math.max(14, state.readerFS - 1);
      applyReaderPrefs();
    };
    const wN = document.getElementById('btn-width-narrow');
    const wW = document.getElementById('btn-width-wide');
    const wF = document.getElementById('btn-width-full');
    if (wN) wN.onclick = () => { state.readerWidth = 560; applyReaderPrefs(); };
    if (wW) wW.onclick = () => { state.readerWidth = 680; applyReaderPrefs(); };
    if (wF) wF.onclick = () => { state.readerWidth = 860; applyReaderPrefs(); };
    const jpBtn = document.getElementById('btn-jp-toggle');
    if (jpBtn) jpBtn.onclick = () => {
      state.readerShowJP = !state.readerShowJP;
      applyReaderPrefs();
      showToast(state.readerShowJP ? 'Japanese lines: shown' : 'Japanese lines: hidden');
    };
    const serifBtn = document.getElementById('btn-serif-toggle');
    if (serifBtn) serifBtn.onclick = () => {
      state.readerSerif = !state.readerSerif;
      applyReaderPrefs();
      showToast(state.readerSerif ? 'Serif font' : 'Sans-serif font');
    };

    DOM.btnSpreadToggle.onclick = toggleSpreadMode;

    DOM.pageInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const raw = DOM.pageInput.value.replace(/[^0-9]/g, '');
        const val = parseInt(raw, 10);
        if (!isNaN(val)) goToPage(val);
      }
    });

    DOM.pageSlider.addEventListener('input', (e) => {
      const page = parseInt(e.target.value, 10);
      DOM.sliderTooltip.textContent = `Page ${page}`;
      DOM.sliderTooltip.style.display = 'block';
      const pct = (page - 1) / (TOTAL_PAGES - 1);
      DOM.sliderTooltip.style.left = `${pct * 100}%`;
    });

    DOM.pageSlider.addEventListener('change', (e) => {
      const page = parseInt(e.target.value, 10);
      DOM.sliderTooltip.style.display = 'none';
      goToPage(page);
    });

    DOM.pageSlider.addEventListener('mouseleave', () => {
      DOM.sliderTooltip.style.display = 'none';
    });

    DOM.btnToc.onclick = () => toggleDrawer(DOM.tocDrawer);
    DOM.btnThumbnails.onclick = () => toggleDrawer(DOM.thumbnailsDrawer);
    DOM.btnSearch.onclick = () => toggleDrawer(DOM.searchDrawer);
    DOM.btnBookmark.onclick = () => toggleDrawer(DOM.bookmarkDrawer);
    DOM.btnTheme.onclick = () => toggleDrawer(DOM.themeDrawer);

    document.querySelectorAll('.drawer-close-btn').forEach(btn => {
      btn.onclick = () => {
        const targetId = btn.getAttribute('data-close');
        if (targetId) document.getElementById(targetId).classList.remove('open');
      };
    });

    document.querySelectorAll('.theme-card').forEach(card => {
      card.onclick = () => {
        const t = card.getAttribute('data-theme');
        setTheme(t);
        showToast(`Theme changed: ${card.querySelector('span').textContent}`);
      };
    });

    DOM.btnAddBookmark.onclick = toggleCurrentBookmark;

    DOM.btnSound.onclick = () => {
      state.soundEnabled = !state.soundEnabled;
      updateSoundUI();
      savePreferences();
      showToast(state.soundEnabled ? 'Page Turn Sound: ON' : 'Page Turn Sound: MUTED');
    };

    DOM.btnAutoFlip.onclick = toggleAutoFlip;

    DOM.btnZoomIn.onclick = () => setZoom(state.zoomLevel + 0.2);
    DOM.btnZoomOut.onclick = () => setZoom(state.zoomLevel - 0.2);
    DOM.btnZoomReset.onclick = resetZoom;

    DOM.flipbookStage.addEventListener('dblclick', (e) => {
      if (state.zoomLevel > 1.0) {
        resetZoom();
      } else {
        setZoom(1.5);
      }
    });

    window.addEventListener('wheel', (e) => {
      if (e.ctrlKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.15 : 0.15;
        setZoom(state.zoomLevel + delta);
      }
    }, { passive: false });

    DOM.flipbookStage.addEventListener('mousedown', (e) => {
      if (state.zoomLevel <= 1.0) return;
      state.isPanning = true;
      state.startPanX = e.clientX - state.panX;
      state.startPanY = e.clientY - state.panY;
    });

    window.addEventListener('mousemove', (e) => {
      if (!state.isPanning) return;
      state.panX = e.clientX - state.startPanX;
      state.panY = e.clientY - state.startPanY;
      applyTransform();
    });

    window.addEventListener('mouseup', () => {
      state.isPanning = false;
    });

    DOM.btnFullscreen.onclick = toggleFullscreen;

    DOM.btnResumeYes.onclick = () => {
      const p = parseInt(DOM.resumePageNum.textContent, 10);
      DOM.resumeBanner.style.display = 'none';
      goToPage(p);
      showToast(`Resumed from Page ${p}`);
    };
    DOM.btnResumeDismiss.onclick = () => {
      DOM.resumeBanner.style.display = 'none';
    };

    DOM.searchInput.addEventListener('input', handleSearchInput);
    window.addEventListener('keydown', handleKeyboardShortcuts);

    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (pageFlipInstance && state.viewMode === 'flip') {
          layoutFlipbook();
        }
      }, 180);
    });
  }

  function handleKeyboardShortcuts(e) {
    if (document.activeElement === DOM.searchInput || document.activeElement === DOM.pageInput) {
      if (e.key === 'Escape') closeAllDrawers();
      return;
    }

    switch(e.key) {
      case 'ArrowLeft':
      case 'a':
      case 'A':
      case 'PageUp':
        e.preventDefault();
        if (pageFlipInstance && state.viewMode === 'flip') pageFlipInstance.flipPrev();
        else if (state.viewMode === 'reader') readerStep(-1);
        else goToPage(state.currentPage - 1);
        break;

      case 'ArrowRight':
      case 'd':
      case 'D':
      case 'PageDown':
      case ' ':
        e.preventDefault();
        if (pageFlipInstance && state.viewMode === 'flip') pageFlipInstance.flipNext();
        else if (state.viewMode === 'reader') readerStep(1);
        else goToPage(state.currentPage + 1);
        break;

      case 'Home':
        e.preventDefault();
        goToPage(1);
        break;

      case 'End':
        e.preventDefault();
        goToPage(TOTAL_PAGES);
        break;

      case 'f':
      case 'F':
        toggleFullscreen();
        break;

      case 't':
      case 'T':
        toggleDrawer(DOM.tocDrawer);
        break;

      case 's':
      case 'S':
        e.preventDefault();
        toggleDrawer(DOM.searchDrawer);
        break;

      case 'b':
      case 'B':
        toggleDrawer(DOM.bookmarkDrawer);
        break;

      case 'j':
      case 'J':
        state.readerShowJP = !state.readerShowJP;
        applyReaderPrefs();
        break;

      case 'm':
      case 'M':
        // Cycle: Reader → Flip → Scroll → Reader
        setViewMode(state.viewMode === 'reader' ? 'flip' : state.viewMode === 'flip' ? 'scroll' : 'reader');
        break;

      case '+':
      case '=':
        if (state.viewMode === 'reader') {
          state.readerFS = Math.min(28, state.readerFS + 1);
          applyReaderPrefs();
        } else setZoom(state.zoomLevel + 0.2);
        break;

      case '-':
      case '_':
        if (state.viewMode === 'reader') {
          state.readerFS = Math.max(14, state.readerFS - 1);
          applyReaderPrefs();
        } else setZoom(state.zoomLevel - 0.2);
        break;

      case '0':
        resetZoom();
        break;

      case 'Escape':
        closeAllDrawers();
        if (state.zoomLevel > 1.0) resetZoom();
        break;
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag));
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
