/* ============================================================
   Pathfinder mock — shared behavior
   - role state (localStorage) chosen on Activate page
   - top nav + footer rendering (role-adaptive)
   - waveform generation / play toggle / heart toggle
   - admin tab switching
   ============================================================ */
(function () {
  'use strict';

  // ─── Role state ─────────────────────────────────────────
  var ROLE = localStorage.getItem('pf_role') || 'guest';

  var ROLE_LABEL = { guest: 'guest', licensee: 'licensee', creator: 'creator', admin: 'admin' };
  var DISPLAY_NAME = { guest: 'Guest', licensee: 'Aoi Tanaka', creator: 'Sa-saT', admin: 'Admin' };

  window.PF = {
    role: ROLE,
    setRole: function (r) { localStorage.setItem('pf_role', r); ROLE = r; },
    isCreator: function () { return ROLE === 'creator' || ROLE === 'admin'; },
    isAdmin: function () { return ROLE === 'admin'; },
    isActivated: function () { return ROLE !== 'guest'; },
  };

  // ─── Top nav rendering ──────────────────────────────────
  function navLink(href, label, opts) {
    opts = opts || {};
    var active = location.pathname.split('/').pop() === href ? ' active' : '';
    var info = opts.info ? '<span class="dot-info"></span>' : '';
    return '<a class="nav-link' + active + '" href="' + href + '">' + label + info + '</a>';
  }

  function renderNav() {
    var host = document.querySelector('[data-nav]');
    if (!host) return;
    var links = '';
    links += navLink('dashboard.html', 'Dashboard');
    if (PF.isAdmin()) {
      links += navLink('admin.html', 'Admin', { info: true });
    } else if (PF.isActivated()) {
      links += navLink('commission.html', 'Commission', { info: ROLE === 'creator' });
    }
    if (PF.isCreator()) links += navLink('uploads.html', 'Uploads');

    var role = ROLE_LABEL[ROLE] || 'guest';
    var roleSide = '';
    if (PF.isActivated()) {
      roleSide =
        '<div class="nav-role">' +
        '<span class="role-chip ' + role + '">' + role + '</span>' +
        '<span class="display-name">' + DISPLAY_NAME[ROLE] + '</span>' +
        '<a href="index.html" title="Deactivate / ロール切替" style="font-size:22px;line-height:1;color:#cf2d56;">⏻</a>' +
        '</div>';
    } else {
      roleSide = '<div class="nav-role"><a href="index.html" style="color:#c0600a;font-weight:600;">Activate</a></div>';
    }

    host.innerHTML =
      '<div class="top-nav-inner">' +
      '<a class="brand" href="dashboard.html"><span class="brand-mark"></span>Pathfinder</a>' +
      '<nav class="top-nav-links">' + links + '</nav>' +
      roleSide +
      '</div>';
  }

  function renderFooter() {
    var f = document.querySelector('[data-footer]');
    if (!f) return;
    f.innerHTML = '<span>© 2026 Pathfinder</span><span class="ver">v0.3.0 · DEMO</span>';
  }

  // ─── Waveform generator ─────────────────────────────────
  function genWave(el, seed) {
    var N = 64, s = seed;
    for (var i = 0; i < N; i++) {
      s = (s * 9301 + 49297) % 233280;
      var r = s / 233280;
      var env = Math.sin((i / N) * Math.PI) * 0.7 + 0.3;
      var h = Math.max(4, Math.floor(env * (10 + r * 38)));
      var bar = document.createElement('div');
      bar.className = 'wave-bar';
      bar.style.height = h + 'px';
      el.appendChild(bar);
    }
  }
  function buildWaves() {
    document.querySelectorAll('.waveform[data-seed]').forEach(function (el) {
      if (el.children.length) return;
      genWave(el, parseInt(el.getAttribute('data-seed'), 10) || 12345);
    });
  }

  // ─── Interactions ───────────────────────────────────────
  function wireInteractions() {
    // play toggle on audio cards
    document.querySelectorAll('.audio-card .play-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var card = btn.closest('.audio-card');
        var was = card.classList.contains('playing');
        document.querySelectorAll('.audio-card.playing').forEach(function (c) {
          c.classList.remove('playing');
          var b = c.querySelector('.play-btn'); if (b) b.textContent = '▶';
        });
        if (!was) { card.classList.add('playing'); btn.textContent = '⏸'; }
      });
    });
    // heart toggle
    document.querySelectorAll('.heart-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        btn.classList.toggle('fav');
        var n = btn.querySelector('span');
        if (n) {
          var v = parseInt(n.textContent, 10) || 0;
          n.textContent = btn.classList.contains('fav') ? v + 1 : Math.max(0, v - 1);
        }
        var svg = btn.querySelector('svg');
        if (svg) svg.setAttribute('fill', btn.classList.contains('fav') ? 'currentColor' : 'none');
      });
    });
    // generic control button groups (sort / page-size / filter)
    document.querySelectorAll('[data-btngroup]').forEach(function (group) {
      group.querySelectorAll('button').forEach(function (b) {
        b.addEventListener('click', function () {
          group.querySelectorAll('button').forEach(function (x) { x.classList.remove('active'); });
          b.classList.add('active');
        });
      });
    });
    // tag picker (uploads)
    document.querySelectorAll('.tag-pick').forEach(function (t) {
      t.addEventListener('click', function () { t.classList.toggle('sel'); });
    });
    // settings toggles
    document.querySelectorAll('.toggle').forEach(function (t) {
      t.addEventListener('click', function () { t.classList.toggle('on'); });
    });
    // chat input (order detail) — append a bubble locally
    var chatForm = document.querySelector('[data-chat-form]');
    if (chatForm) {
      chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = chatForm.querySelector('input');
        var text = (input.value || '').trim();
        if (!text) return;
        var scroll = document.querySelector('.chat-scroll');
        var wrap = document.createElement('div');
        wrap.className = 'msg mine';
        wrap.innerHTML = '<div class="bubble">' + text.replace(/</g, '&lt;') + '</div>' +
          '<span class="msg-time">今</span>';
        scroll.appendChild(wrap);
        input.value = '';
        scroll.scrollTop = scroll.scrollHeight;
      });
    }
  }

  // ─── Admin tabs ─────────────────────────────────────────
  function wireTabs() {
    document.querySelectorAll('.tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        var key = tab.getAttribute('data-tab');
        document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
        document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.remove('active'); });
        tab.classList.add('active');
        var panel = document.querySelector('.tab-panel[data-panel="' + key + '"]');
        if (panel) panel.classList.add('active');
      });
    });
  }

  // ─── Role-scoped visibility ─────────────────────────────
  function applyRoleVisibility() {
    document.querySelectorAll('[data-role-only]').forEach(function (el) {
      var roles = el.getAttribute('data-role-only').split(/[\s,]+/);
      var ok = roles.indexOf(ROLE) !== -1 ||
        (roles.indexOf('creator+') !== -1 && PF.isCreator()) ||
        (roles.indexOf('activated') !== -1 && PF.isActivated());
      el.style.display = ok ? '' : 'none';
    });
    // role-text substitution
    document.querySelectorAll('[data-role-text]').forEach(function (el) {
      var map = { display: DISPLAY_NAME[ROLE], role: ROLE_LABEL[ROLE] };
      el.textContent = map[el.getAttribute('data-role-text')] || el.textContent;
    });
  }

  // ─── Boot ───────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    renderNav();
    renderFooter();
    applyRoleVisibility();
    buildWaves();
    wireInteractions();
    wireTabs();
  });
})();
