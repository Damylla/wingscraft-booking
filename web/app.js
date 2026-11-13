'use strict';

const state = {
  service: null,
  date: '',
  time: '',
  name: '',
  email: '',
  services: [],
  step: 1,
  viewYear: new Date().getFullYear(),
  viewMonth: new Date().getMonth() + 1, // 1..12
  monthDays: {}, // { 'YYYY-MM-DD': { status, available_count } }
  monthLoading: false
};

let slotRequestSeq = 0;
let slotAbortController = null;
let monthRequestSeq = 0;

const $ = id => document.getElementById(id);

function todayIso() {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0')
  ].join('-');
}

function yearMonthStr(year, month) {
  return `${year}-${String(month).padStart(2, '0')}`;
}

function formatDate(isoDate) {
  if (!isoDate) return '—';
  const d = new Date(isoDate + 'T12:00:00');
  if (Number.isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

function formatShortDate(isoDate) {
  if (!isoDate) return '';
  const d = new Date(isoDate + 'T12:00:00');
  if (Number.isNaN(d.getTime())) return isoDate;
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
}

function formatTimeRange(startTime, durationMinutes) {
  if (!startTime) return '—';
  const parts = startTime.split(':');
  if (parts.length !== 2) return startTime;
  const totalStart = Number(parts[0]) * 60 + Number(parts[1]);
  const totalEnd = totalStart + Number(durationMinutes || 30);
  const endH = String(Math.floor(totalEnd / 60) % 24).padStart(2, '0');
  const endM = String(totalEnd % 60).padStart(2, '0');
  return `${startTime} – ${endH}:${endM}`;
}

function notice(message, type = 'error') {
  const elNode = $('notice');
  if (!elNode) return;
  elNode.textContent = message || '';
  elNode.dataset.type = type;
  elNode.hidden = !message;
}

async function api(path, options = {}) {
  const response = await fetch(path, { cache: 'no-store', ...options });
  let result;
  try {
    result = await response.json();
  } catch {
    throw Error('Unable to reach booking server');
  }
  if (!response.ok) {
    throw Error(result.error || 'Request failed');
  }
  return result;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function canReachStep(targetStep) {
  if (targetStep <= 1) return true;
  if (targetStep >= 2 && !state.service) return false;
  if (targetStep >= 3 && (!state.date || !state.time)) return false;
  if (targetStep >= 4 && !isCustomerValid(false)) return false;
  return true;
}

function updateStepIndicators(currentStep, isComplete = false) {
  const pills = document.querySelectorAll('#step-indicator .step-pill');
  pills.forEach(pill => {
    const stepNum = Number(pill.dataset.step);
    const btn = pill.querySelector('.step-pill-btn');
    const numSpan = pill.querySelector('.step-pill-num');
    const isCompleted = isComplete || stepNum < currentStep;
    const isActive = !isComplete && stepNum === currentStep;

    pill.classList.toggle('active', isActive);
    pill.classList.toggle('completed', isCompleted);

    if (numSpan) {
      numSpan.textContent = isCompleted ? '✓' : `0${stepNum}`;
    }
    if (btn) {
      if (isActive) {
        btn.setAttribute('aria-current', 'step');
      } else {
        btn.removeAttribute('aria-current');
      }
      btn.disabled = isComplete || !canReachStep(stepNum);
    }
  });
}

function showStep(n, scroll = true) {
  state.step = n;
  notice('');

  ['step1', 'step2', 'step3', 'step4'].forEach((id, i) => {
    const stepEl = $(id);
    if (!stepEl) return;
    const active = i + 1 === n;
    stepEl.hidden = !active;
    if (active) {
      stepEl.classList.remove('step-enter');
      void stepEl.offsetWidth;
      stepEl.classList.add('step-enter');
    }
  });

  $('success').hidden = true;
  $('step-label').textContent = `STEP 0${n} / 04`;
  $('progress-fill').style.width = `${(n * 100) / 4}%`;
  updateStepIndicators(n, false);

  if (n === 2) {
    if (state.service) {
      $('selected-service').textContent = `${state.service.name} · ${state.service.duration_minutes} min`;
    }
    renderCalendarGrid();
  }
  if (n === 3) {
    renderSummary();
  }
  if (n === 4) {
    renderSummary();
    renderReview();
  }

  if (scroll) {
    const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    $('booking-heading').scrollIntoView({
      behavior: prefersReduced ? 'auto' : 'smooth',
      block: 'start'
    });
  }
}

/* ---------------- STEP 1: SERVICES ---------------- */
function getServiceDescription(service) {
  const mins = service.duration_minutes;
  if (mins <= 30) return 'Focused one-on-one session tailored to your immediate goals.';
  if (mins <= 60) return 'Comprehensive session with dedicated time for strategy and execution.';
  return 'Extended deep-dive studio session for complex projects and planning.';
}

function renderServices() {
  const target = $('services');
  target.replaceChildren();

  const countLabel = $('service-count-label');
  if (countLabel) {
    countLabel.textContent = state.services.length
      ? `${state.services.length} ${state.services.length === 1 ? 'offering' : 'offerings'} available`
      : '';
  }

  if (!state.services.length) {
    target.append(el('p', 'hint', 'No services available right now.'));
    return;
  }

  state.services.forEach((s, i) => {
    const isSelected = state.service?.id === s.id;
    const b = el('button', 'service-option' + (isSelected ? ' selected' : ''));
    b.type = 'button';
    b.style.setProperty('--item-idx', String(i));
    b.setAttribute('aria-pressed', String(isSelected));

    const topRow = el('div', 'service-card-top');
    topRow.append(el('span', 'number', String(i + 1).padStart(2, '0') + ' / SERVICE'));
    const checkBadge = el('span', 'check', isSelected ? '✓' : '');
    checkBadge.setAttribute('aria-hidden', 'true');
    topRow.append(checkBadge);

    const title = el('span', 'service-title', s.name);
    const desc = el('span', 'service-desc', getServiceDescription(s));
    const footer = el('div', 'service-card-footer');
    footer.append(
      el('span', 'duration-pill', `${s.duration_minutes} min session`),
      el('span', 'service-cta', isSelected ? 'Selected' : 'Select →')
    );

    b.append(topRow, title, desc, footer);

    b.addEventListener('click', () => {
      const changed = state.service?.id !== s.id;
      state.service = s;
      if (changed) {
        state.time = '';
      }
      $('next1').disabled = false;
      const statusEl = $('step1-status');
      if (statusEl) {
        statusEl.textContent = `Selected: ${s.name} (${s.duration_minutes} min)`;
      }
      renderServices();
      updateStepIndicators(state.step);
    });

    target.append(b);
  });
}

/* ---------------- STEP 2: CUSTOM CALENDAR & SLOTS ---------------- */
function canGoPrevMonth() {
  const now = new Date();
  return (
    state.viewYear > now.getFullYear() ||
    (state.viewYear === now.getFullYear() && state.viewMonth > now.getMonth() + 1)
  );
}

function updateCalendarNavState() {
  const prevBtn = $('cal-prev');
  if (prevBtn) {
    prevBtn.disabled = !canGoPrevMonth();
  }
  const monthLabel = $('cal-month-label');
  if (monthLabel) {
    const d = new Date(state.viewYear, state.viewMonth - 1, 1);
    monthLabel.textContent = d.toLocaleDateString('en-US', {
      month: 'long',
      year: 'numeric'
    });
  }
}

async function loadMonthAvailability(year, month, autoSelectDate = false) {
  if (!state.service) return;
  const seq = ++monthRequestSeq;
  state.monthLoading = true;
  updateCalendarNavState();
  renderCalendarGrid();

  const ym = yearMonthStr(year, month);
  try {
    const data = await api(
      `/api/availability?service_id=${state.service.id}&month=${encodeURIComponent(ym)}`
    );
    if (seq !== monthRequestSeq) return;
    if (data && data.days) {
      Object.assign(state.monthDays, data.days);
    }
    state.monthLoading = false;

    if (autoSelectDate) {
      const currentInfo = state.date ? state.monthDays[state.date] : null;
      if (!state.date || !currentInfo || currentInfo.status !== 'available') {
        const firstAvailable = Object.keys(data.days || {})
          .sort()
          .find(dayIso => data.days[dayIso]?.status === 'available');
        if (firstAvailable) {
          selectDate(firstAvailable, false);
        } else if (state.date) {
          refreshSlots();
        }
      } else {
        refreshSlots();
      }
    }
    renderCalendarGrid();
  } catch {
    if (seq !== monthRequestSeq) return;
    state.monthLoading = false;
    renderCalendarGrid();
    if (autoSelectDate && state.date) {
      refreshSlots();
    }
  }
}

function renderCalendarGrid() {
  updateCalendarNavState();
  const grid = $('cal-grid');
  if (!grid) return;
  grid.replaceChildren();

  const year = state.viewYear;
  const month = state.viewMonth; // 1..12
  const firstDayOfMonth = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  // Convert Sunday=0..Saturday=6 into Monday=0..Sunday=6
  const startOffset = (firstDayOfMonth.getDay() + 6) % 7;
  const todayStr = todayIso();

  for (let i = 0; i < startOffset; i++) {
    const emptyCell = el('div', 'cal-cell empty');
    emptyCell.setAttribute('aria-hidden', 'true');
    grid.append(emptyCell);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const isPast = iso < todayStr;
    const isToday = iso === todayStr;
    const isSelected = iso === state.date;
    const dayMeta = state.monthDays[iso];

    let status = 'available';
    if (isPast) {
      status = 'past';
    } else if (dayMeta) {
      status = dayMeta.status;
    } else if (state.monthLoading) {
      status = 'loading';
    }

    const isBookable = !isPast && status === 'available';

    const btn = el(
      'button',
      [
        'cal-day',
        `status-${status}`,
        isSelected ? 'selected' : '',
        isToday ? 'today' : ''
      ]
        .filter(Boolean)
        .join(' ')
    );
    btn.type = 'button';
    btn.dataset.date = iso;
    btn.disabled = !isBookable;
    btn.setAttribute('aria-pressed', String(isSelected));
    btn.setAttribute('aria-disabled', String(!isBookable));

    const labelParts = [formatDate(iso)];
    if (isToday) labelParts.push('(Today)');
    if (isPast) {
      labelParts.push('— Past date, unavailable');
    } else if (status === 'available' && dayMeta) {
      labelParts.push(`— ${dayMeta.available_count} slots available`);
    } else if (status !== 'available' && status !== 'loading') {
      labelParts.push('— Unavailable');
    }
    btn.setAttribute('aria-label', labelParts.join(' '));

    const numEl = el('span', 'cal-day-num', String(day));
    const dotEl = el('span', 'cal-day-dot');
    dotEl.setAttribute('aria-hidden', 'true');
    btn.append(numEl, dotEl);

    if (isBookable) {
      btn.addEventListener('click', () => {
        selectDate(iso, true);
      });
    }

    grid.append(btn);
  }
}

function selectDate(isoDate, userInitiated = true) {
  if (!isoDate) return;
  const changed = state.date !== isoDate;
  state.date = isoDate;
  const dateInput = $('date');
  if (dateInput && dateInput.value !== isoDate) {
    dateInput.value = isoDate;
  }

  const [y, m] = isoDate.split('-').map(Number);
  if (y && m && (y !== state.viewYear || m !== state.viewMonth)) {
    state.viewYear = y;
    state.viewMonth = m;
    loadMonthAvailability(y, m, false);
  }

  renderCalendarGrid();
  if (changed || userInitiated) {
    refreshSlots();
  }
}

function setupCalendarKeyboardNav() {
  const grid = $('cal-grid');
  if (!grid) return;

  grid.addEventListener('keydown', e => {
    const activeBtn = document.activeElement;
    if (!activeBtn || !activeBtn.classList.contains('cal-day')) return;

    const enabledDays = [...grid.querySelectorAll('.cal-day:not(:disabled)')];
    if (!enabledDays.length) return;
    const idx = enabledDays.indexOf(activeBtn);
    if (idx === -1) return;

    let targetIdx = idx;
    if (e.key === 'ArrowRight') {
      targetIdx = Math.min(enabledDays.length - 1, idx + 1);
    } else if (e.key === 'ArrowLeft') {
      targetIdx = Math.max(0, idx - 1);
    } else if (e.key === 'ArrowDown') {
      targetIdx = Math.min(enabledDays.length - 1, idx + 5);
    } else if (e.key === 'ArrowUp') {
      targetIdx = Math.max(0, idx - 5);
    } else if (e.key === 'Home') {
      targetIdx = 0;
    } else if (e.key === 'End') {
      targetIdx = enabledDays.length - 1;
    } else {
      return;
    }

    e.preventDefault();
    enabledDays[targetIdx].focus();
  });
}

function updateSelectedSlotUI() {
  const banner = $('selected-slot-banner');
  const bannerText = $('selected-slot-text');
  const statusHint = $('step2-status');
  const nextBtn = $('next2');

  if (state.time && state.date && state.service) {
    const range = formatTimeRange(state.time, state.service.duration_minutes);
    if (banner && bannerText) {
      banner.hidden = false;
      bannerText.textContent = `${formatShortDate(state.date)} · ${range}`;
    }
    if (statusHint) {
      statusHint.textContent = `Selected ${range}`;
    }
    if (nextBtn) {
      nextBtn.disabled = false;
    }
  } else {
    if (banner) banner.hidden = true;
    if (statusHint) statusHint.textContent = 'Select a time slot to continue';
    if (nextBtn) nextBtn.disabled = true;
  }
  updateStepIndicators(state.step);
}

function renderSlotSkeletons(target) {
  target.replaceChildren();
  for (let i = 0; i < 9; i++) {
    const sk = el('div', 'slot-skeleton');
    sk.setAttribute('aria-hidden', 'true');
    target.append(sk);
  }
}

async function refreshSlots() {
  const previousTime = state.time;
  state.time = '';
  updateSelectedSlotUI();

  const target = $('slots');
  const dateHeading = $('slot-date-heading');
  const badge = $('slot-count-badge');

  if (!state.date || !state.service) {
    if (dateHeading) dateHeading.textContent = 'Select a date on the calendar';
    if (badge) badge.hidden = true;
    target.replaceChildren(el('p', 'hint', 'Select a date first to view available times.'));
    return;
  }

  if (dateHeading) {
    dateHeading.textContent = formatDate(state.date);
  }
  if (badge) {
    badge.hidden = false;
    badge.textContent = 'Checking…';
    badge.className = 'slot-count-badge loading';
  }

  // Cancel any in-flight slot request and track sequence to prevent stale updates
  if (slotAbortController) {
    slotAbortController.abort();
  }
  slotAbortController = new AbortController();
  const reqId = ++slotRequestSeq;
  const requestedDate = state.date;
  const requestedServiceId = state.service.id;

  renderSlotSkeletons(target);

  try {
    const data = await api(
      `/api/availability?service_id=${requestedServiceId}&date=${encodeURIComponent(requestedDate)}`,
      { signal: slotAbortController.signal }
    );

    // Prevent stale availability responses from replacing newer results
    if (
      reqId !== slotRequestSeq ||
      state.date !== requestedDate ||
      state.service?.id !== requestedServiceId
    ) {
      return;
    }

    const availableTimes = data.available_times || [];
    const unavailableTimes = data.unavailable_times || [];

    // Sync calendar day cache with exact slot count
    state.monthDays[requestedDate] = {
      status: availableTimes.length > 0 ? 'available' : (data.day_status || 'unavailable'),
      available_count: availableTimes.length
    };
    renderCalendarGrid();

    target.replaceChildren();

    if (badge) {
      badge.hidden = false;
      badge.className = 'slot-count-badge' + (availableTimes.length ? ' has-slots' : ' empty');
      badge.textContent = availableTimes.length
        ? `${availableTimes.length} ${availableTimes.length === 1 ? 'slot' : 'slots'} open`
        : 'No slots open';
    }

    if (!availableTimes.length) {
      const emptyBox = el('div', 'slot-empty-state');
      const reasonText =
        data.day_status === 'closed'
          ? 'The studio is closed on this day.'
          : data.day_status === 'blocked'
          ? 'This date is reserved or unavailable for bookings.'
          : 'No available times remain on this date.';
      emptyBox.append(
        el('div', 'slot-empty-icon', '◌'),
        el('p', 'slot-empty-title', reasonText),
        el('p', 'hint', 'Please choose another highlighted date on the calendar.')
      );

      const nextAvailIso = Object.keys(state.monthDays)
        .sort()
        .find(d => d > requestedDate && state.monthDays[d]?.status === 'available');
      if (nextAvailIso) {
        const jumpBtn = el('button', 'btn ghost btn-sm', `Jump to ${formatShortDate(nextAvailIso)} →`);
        jumpBtn.type = 'button';
        jumpBtn.addEventListener('click', () => selectDate(nextAvailIso, true));
        emptyBox.append(jumpBtn);
      }
      target.append(emptyBox);
      return;
    }

    // Combine available and unavailable slots in chronological order for clarity
    const allSlotsMap = new Map();
    availableTimes.forEach(t => allSlotsMap.set(t, true));
    unavailableTimes.forEach(t => {
      if (!allSlotsMap.has(t)) allSlotsMap.set(t, false);
    });
    const sortedTimes = [...allSlotsMap.keys()].sort();

    sortedTimes.forEach((time, index) => {
      const isAvailable = allSlotsMap.get(time);
      const button = el(
        'button',
        'slot' + (isAvailable ? '' : ' unavailable'),
        time
      );
      button.type = 'button';
      button.style.setProperty('--slot-idx', String(index));

      if (!isAvailable) {
        button.disabled = true;
        button.setAttribute('aria-disabled', 'true');
        button.setAttribute('aria-label', `${time} — Unavailable`);
        button.title = 'Unavailable';
      } else {
        const isRestored = previousTime === time;
        button.setAttribute('aria-pressed', String(isRestored));
        button.setAttribute(
          'aria-label',
          `${formatTimeRange(time, state.service.duration_minutes)} available`
        );
        if (isRestored) {
          button.classList.add('selected');
          state.time = time;
        }
        button.addEventListener('click', () => {
          state.time = time;
          target.querySelectorAll('button.slot:not(:disabled)').forEach(node => {
            const active = node === button;
            node.classList.toggle('selected', active);
            node.setAttribute('aria-pressed', String(active));
          });
          updateSelectedSlotUI();
        });
      }
      target.append(button);
    });

    updateSelectedSlotUI();
  } catch (e) {
    if (e.name === 'AbortError' || reqId !== slotRequestSeq) return;
    if (badge) badge.hidden = true;
    target.replaceChildren(el('p', 'hint', e.message));
  }
}

function setupSlotKeyboardNav() {
  const container = $('slots');
  if (!container) return;
  container.addEventListener('keydown', e => {
    const active = document.activeElement;
    if (!active || !active.classList.contains('slot')) return;
    const buttons = [...container.querySelectorAll('button.slot:not(:disabled)')];
    const idx = buttons.indexOf(active);
    if (idx === -1) return;

    let nextIdx = idx;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      nextIdx = (idx + 1) % buttons.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      nextIdx = (idx - 1 + buttons.length) % buttons.length;
    } else {
      return;
    }
    e.preventDefault();
    buttons[nextIdx].focus();
  });
}

/* ---------------- STEP 3: CUSTOMER DETAILS & SUMMARY ---------------- */
function isCustomerValid(showErrors = true) {
  const nameInput = $('name');
  const emailInput = $('email');
  const nameError = $('name-error');
  const emailError = $('email-error');

  const nameVal = (nameInput?.value || '').trim();
  const emailVal = (emailInput?.value || '').trim();

  let valid = true;

  if (!nameVal || nameVal.length > 100) {
    valid = false;
    if (showErrors && nameError) {
      nameError.textContent = 'Please enter your full name (1–100 characters).';
      nameError.hidden = false;
      nameInput?.classList.add('input-invalid');
    }
  } else if (nameError) {
    nameError.hidden = true;
    nameInput?.classList.remove('input-invalid');
  }

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailVal || emailVal.length > 254 || !emailPattern.test(emailVal)) {
    valid = false;
    if (showErrors && emailError) {
      emailError.textContent = 'Please enter a valid email address (e.g. name@example.com).';
      emailError.hidden = false;
      emailInput?.classList.add('input-invalid');
    }
  } else if (emailError) {
    emailError.hidden = true;
    emailInput?.classList.remove('input-invalid');
  }

  if (valid) {
    state.name = nameVal;
    state.email = emailVal;
  }

  return valid;
}

function renderSummary() {
  const dl = $('summary');
  if (!dl || !state.service) return;
  dl.replaceChildren();

  const items = [
    ['Service', state.service.name],
    ['Date', formatDate(state.date)],
    ['Time', formatTimeRange(state.time, state.service.duration_minutes)],
    ['Duration', `${state.service.duration_minutes} minutes`]
  ];

  const currentName = ($('name')?.value || '').trim();
  const currentEmail = ($('email')?.value || '').trim();
  if (currentName) items.push(['Guest', currentName]);
  if (currentEmail) items.push(['Email', currentEmail]);

  items.forEach(([key, value]) => {
    const row = el('div', 'summary-item');
    row.append(el('dt', '', key), el('dd', '', value));
    dl.append(row);
  });
}

/* ---------------- STEP 4: REVIEW & CONFIRM ---------------- */
function renderReview() {
  if (!state.service) return;
  $('review-service').textContent = state.service.name;
  $('review-duration').textContent = `${state.service.duration_minutes} minute session`;
  $('review-datetime').textContent = `${formatDate(state.date)} · ${formatTimeRange(
    state.time,
    state.service.duration_minutes
  )}`;
  $('review-name').textContent = ($('name')?.value || '').trim();
  $('review-email').textContent = ($('email')?.value || '').trim();
}

async function init() {
  const todayStr = todayIso();
  const [initY, initM] = todayStr.split('-').map(Number);
  state.viewYear = initY;
  state.viewMonth = initM;

  const dateInput = $('date');
  if (dateInput) {
    dateInput.min = todayStr;
    dateInput.value = todayStr;
    state.date = todayStr;
  }

  setupCalendarKeyboardNav();
  setupSlotKeyboardNav();

  try {
    state.services = (await api('/api/services')).services;
    renderServices();
  } catch (e) {
    notice('Could not load services: ' + e.message);
  }

  // Step indicator direct navigation
  document.querySelectorAll('#step-indicator .step-pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetStep = Number(btn.dataset.stepTarget);
      if (canReachStep(targetStep)) {
        showStep(targetStep);
      }
    });
  });

  // Step 1 -> Step 2
  $('next1').addEventListener('click', () => {
    if (!state.service) return;
    showStep(2);
    loadMonthAvailability(state.viewYear, state.viewMonth, true);
  });

  $('change-service-btn')?.addEventListener('click', () => showStep(1));

  // Calendar navigation
  $('cal-prev')?.addEventListener('click', () => {
    if (!canGoPrevMonth()) return;
    state.viewMonth -= 1;
    if (state.viewMonth < 1) {
      state.viewMonth = 12;
      state.viewYear -= 1;
    }
    loadMonthAvailability(state.viewYear, state.viewMonth, false);
  });

  $('cal-next')?.addEventListener('click', () => {
    state.viewMonth += 1;
    if (state.viewMonth > 12) {
      state.viewMonth = 1;
      state.viewYear += 1;
    }
    loadMonthAvailability(state.viewYear, state.viewMonth, false);
  });

  $('cal-today')?.addEventListener('click', () => {
    const now = new Date();
    state.viewYear = now.getFullYear();
    state.viewMonth = now.getMonth() + 1;
    loadMonthAvailability(state.viewYear, state.viewMonth, true);
  });

  // Keep native #date input synced if changed programmatically or via assistive tech
  $('date').addEventListener('change', e => {
    if (e.target.value) {
      selectDate(e.target.value, true);
    }
  });

  // Step 2 -> Step 3 / Back
  $('next2').addEventListener('click', () => {
    if (state.date && state.time) {
      showStep(3);
    }
  });
  $('back2').addEventListener('click', () => showStep(1));

  // Step 3 live validation & navigation
  ['name', 'email'].forEach(id => {
    const input = $(id);
    if (!input) return;
    input.addEventListener('input', () => {
      if (input.classList.contains('input-invalid')) {
        isCustomerValid(true);
      } else {
        isCustomerValid(false);
      }
      renderSummary();
      updateStepIndicators(state.step);
    });
  });

  $('back3').addEventListener('click', () => showStep(2));
  $('next3').addEventListener('click', () => {
    if (!isCustomerValid(true)) {
      const firstInvalid = document.querySelector('#step3 .input-invalid');
      firstInvalid?.focus();
      return;
    }
    showStep(4);
  });

  // Step 4 Review quick-edit links & Back
  document.querySelectorAll('[data-edit-step]').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetStep = Number(btn.dataset.editStep);
      showStep(targetStep);
    });
  });

  $('back4').addEventListener('click', () => showStep(3));

  // Final Confirmation Submit
  $('booking-form').addEventListener('submit', async e => {
    e.preventDefault();
    if (!isCustomerValid(true)) {
      showStep(3);
      return;
    }

    const button = $('confirm');
    const originalText = button.innerHTML;
    button.disabled = true;
    button.textContent = 'Confirming reservation…';
    notice('');

    try {
      const customerName = $('name').value.trim();
      const customerEmail = $('email').value.trim();
      const result = await api('/api/bookings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          service_id: state.service.id,
          customer_name: customerName,
          customer_email: customerEmail,
          start_at: state.date + 'T' + state.time
        })
      });

      ['step1', 'step2', 'step3', 'step4'].forEach(id => {
        const elNode = $(id);
        if (elNode) elNode.hidden = true;
      });
      $('progress-fill').style.width = '100%';
      $('step-label').textContent = 'COMPLETE';
      updateStepIndicators(4, true);
      $('success').hidden = false;

      const confirm = $('confirmation');
      confirm.replaceChildren();
      [
        ['Booking reference', '#' + result.booking_id],
        ['Service', `${state.service.name} (${state.service.duration_minutes} min)`],
        ['Date', formatDate(state.date)],
        ['Time', formatTimeRange(state.time, state.service.duration_minutes)],
        ['Customer', customerName],
        ['Email', customerEmail]
      ].forEach(([label, value]) => {
        const line = el('div', 'confirmation-row');
        line.append(el('strong', '', label + ': '), el('span', '', value));
        confirm.append(line);
      });

      const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
      $('success').scrollIntoView({
        behavior: prefersReduced ? 'auto' : 'smooth',
        block: 'center'
      });
    } catch (err) {
      notice(err.message);
      if (/already booked|outside availability/i.test(err.message)) {
        showStep(2);
        await loadMonthAvailability(state.viewYear, state.viewMonth, false);
        await refreshSlots();
        notice('That slot is no longer available. Please choose another time.');
      }
    } finally {
      button.disabled = false;
      button.innerHTML = originalText;
    }
  });

  // Restart flow
  $('restart').addEventListener('click', () => {
    state.service = null;
    state.time = '';
    state.name = '';
    state.email = '';
    $('booking-form').reset();
    if ($('name')) $('name').value = '';
    if ($('email')) $('email').value = '';
    $('next1').disabled = true;
    const statusEl = $('step1-status');
    if (statusEl) statusEl.textContent = 'Choose a service to continue';
    renderServices();
    showStep(1);
  });
  // Gentle pointer-responsive parallax on desktop hero Time Orbit
  const heroEl = $('hero-section');
  if (heroEl) {
    const canParallax = () =>
      window.innerWidth > 900 && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    heroEl.addEventListener('pointermove', e => {
      if (!canParallax()) return;
      const rect = heroEl.getBoundingClientRect();
      const nx = (e.clientX - rect.left) / rect.width - 0.5;
      const ny = (e.clientY - rect.top) / rect.height - 0.5;
      heroEl.style.setProperty('--px', `${(nx * -16).toFixed(1)}px`);
      heroEl.style.setProperty('--py', `${(ny * -12).toFixed(1)}px`);
    });
    heroEl.addEventListener('pointerleave', () => {
      heroEl.style.setProperty('--px', '0px');
      heroEl.style.setProperty('--py', '0px');
    });
  }
}

init();
