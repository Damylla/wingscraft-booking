'use strict';

const $ = id => document.getElementById(id);
const names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
let token = sessionStorage.getItem('wingscraft_admin_key') || '';

const adminState = {
  bookings: [],
  services: [],
  days: [],
  schedule: [],
  filterSearch: '',
  filterDate: '',
  filterStatus: 'all',
  datePreset: 'all'
};

function el(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}

function todayIso() {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0')
  ].join('-');
}

function formatAdminDate(isoDate) {
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

function alertUser(message, good = false) {
  const node = $('admin-alert');
  if (!node) return;
  node.hidden = !message;
  node.textContent = message || '';
  node.dataset.type = good ? 'good' : 'error';
  node.style.background = good ? '#2a3724' : '#4a2b24';
  node.style.borderColor = good ? '#7d9267' : '#aa7666';
}

async function api(path, method = 'GET', body) {
  const response = await fetch(path, {
    method,
    cache: 'no-store',
    headers: {
      Authorization: 'Bearer ' + token,
      ...(body ? { 'Content-Type': 'application/json' } : {})
    },
    ...(body ? { body: JSON.stringify(body) } : {})
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error('Unable to parse server response');
  }
  if (!response.ok) throw Error(data.error || 'Request failed');
  return data;
}

async function load() {
  try {
    const [bookingData, days, services, schedule] = await Promise.all([
      api('/api/admin/bookings'),
      api('/api/admin/blocked-days'),
      api('/api/services'),
      api('/api/admin/schedule')
    ]);
    adminState.bookings = bookingData.bookings || [];
    adminState.days = days.days || [];
    adminState.services = services.services || [];
    adminState.schedule = schedule.schedule || [];

    $('login').hidden = true;
    $('dashboard').hidden = false;
    $('logout').hidden = false;

    renderBookings(adminState.bookings, adminState.services);
    renderDays(adminState.days);
    renderServices(adminState.services);
    renderSchedule(adminState.schedule);
    alertUser('');
  } catch (err) {
    if (/admin key|unauthorized/i.test(err.message)) {
      logout(false);
      alertUser('Invalid admin key. Please try again.');
    } else {
      alertUser(err.message);
    }
  }
}

function logout(clear = true) {
  token = '';
  sessionStorage.removeItem('wingscraft_admin_key');
  $('dashboard').hidden = true;
  $('login').hidden = false;
  $('logout').hidden = true;
  if (clear) alertUser('');
}

function getFilteredBookings() {
  const q = adminState.filterSearch.trim().toLowerCase();
  const dateFilter = adminState.filterDate;
  const statusFilter = adminState.filterStatus;
  const preset = adminState.datePreset;
  const todayStr = todayIso();

  return adminState.bookings.filter(b => {
    const bDate = (b.start_at || '').slice(0, 10);
    if (statusFilter !== 'all' && b.status !== statusFilter) return false;
    if (dateFilter && bDate !== dateFilter) return false;
    if (!dateFilter) {
      if (preset === 'today' && bDate !== todayStr) return false;
      if (preset === 'upcoming' && bDate < todayStr) return false;
    }
    if (q) {
      const serviceName = (
        adminState.services.find(s => s.id === b.service_id)?.name || ''
      ).toLowerCase();
      const refStr = `#${b.id}`;
      const match =
        (b.customer_name || '').toLowerCase().includes(q) ||
        (b.customer_email || '').toLowerCase().includes(q) ||
        serviceName.includes(q) ||
        refStr.includes(q) ||
        String(b.id) === q;
      if (!match) return false;
    }
    return true;
  });
}

function updateFilterUIState() {
  const hasActiveFilter =
    Boolean(adminState.filterSearch.trim()) ||
    Boolean(adminState.filterDate) ||
    adminState.filterStatus !== 'all' ||
    adminState.datePreset !== 'all';

  const clearBtn = $('clear-filters');
  if (clearBtn) clearBtn.hidden = !hasActiveFilter;

  document.querySelectorAll('[data-date-preset]').forEach(btn => {
    btn.classList.toggle(
      'active',
      !adminState.filterDate && btn.dataset.datePreset === adminState.datePreset
    );
  });
}

function renderBookings(bookings = adminState.bookings, services = adminState.services) {
  $('total').textContent = bookings.length;
  $('confirmed').textContent = bookings.filter(b => b.status === 'confirmed').length;
  $('cancelled').textContent = bookings.filter(b => b.status === 'cancelled').length;

  updateFilterUIState();
  const filtered = getFilteredBookings();
  const countBadge = $('booking-count-badge');
  if (countBadge) {
    countBadge.textContent =
      filtered.length === bookings.length
        ? `${bookings.length} total`
        : `${filtered.length} of ${bookings.length} shown`;
  }

  const target = $('booking-rows');
  target.replaceChildren();

  if (!filtered.length) {
    const row = el('tr', 'empty-table-row');
    const td = el('td', 'empty-cell');
    td.colSpan = 6;
    const msg = bookings.length
      ? 'No reservations match your current filter criteria.'
      : 'No reservations have been created yet.';
    td.append(el('div', 'empty-state-box', msg));
    row.append(td);
    target.append(row);
    return;
  }

  filtered.forEach(b => {
    const tr = el('tr', b.status === 'cancelled' ? 'row-cancelled' : '');

    // Reference column
    const refTd = el('td');
    refTd.dataset.label = 'Reference';
    refTd.append(el('span', 'ref-badge', '#' + b.id));

    // Customer column
    const nameTd = el('td');
    nameTd.dataset.label = 'Customer';
    nameTd.append(
      el('strong', 'customer-name-cell', b.customer_name),
      el('small', '', b.customer_email)
    );

    // Service column
    const svc = services.find(s => s.id === b.service_id);
    const serviceTd = el('td');
    serviceTd.dataset.label = 'Service';
    serviceTd.append(
      el('span', 'service-name-cell', svc ? svc.name : 'Service #' + b.service_id)
    );
    if (svc) {
      serviceTd.append(el('small', '', `${svc.duration_minutes} min session`));
    }

    // Date & Time column
    const dateTd = el('td');
    dateTd.dataset.label = 'Date & Time';
    const [bDay, bStartTime] = (b.start_at || '').split('T');
    const bEndTime = (b.end_at || '').split('T')[1] || '';
    dateTd.append(
      el('span', 'date-cell-main', formatAdminDate(bDay)),
      el('small', '', bEndTime ? `${bStartTime} – ${bEndTime}` : bStartTime)
    );

    // Status column
    const stTd = el('td');
    stTd.dataset.label = 'Status';
    stTd.append(
      el('span', 'status ' + (b.status === 'cancelled' ? 'cancelled' : ''), b.status)
    );

    // Action column
    const actionTd = el('td');
    actionTd.dataset.label = 'Action';
    if (b.status === 'confirmed') {
      const cancel = el('button', 'btn ghost btn-cancel-action', 'Cancel');
      cancel.type = 'button';
      cancel.addEventListener('click', async () => {
        if (!confirm(`Cancel reservation #${b.id} for ${b.customer_name}?`)) return;
        cancel.disabled = true;
        try {
          await api('/api/admin/bookings/' + b.id + '/cancel', 'POST');
          await load();
          alertUser(`Reservation #${b.id} cancelled.`, true);
        } catch (e) {
          cancel.disabled = false;
          alertUser(e.message);
        }
      });
      actionTd.append(cancel);
    } else {
      actionTd.append(el('span', 'muted-dash', '—'));
    }

    tr.append(refTd, nameTd, serviceTd, dateTd, stTd, actionTd);
    target.append(tr);
  });
}

function renderDays(days) {
  const target = $('blocked-list');
  target.replaceChildren();
  if (!days.length) {
    target.append(el('p', 'hint', 'No blocked dates configured.'));
    return;
  }
  days.forEach(d => {
    const item = el('div', 'blocked-item');
    const desc = el('div', 'blocked-item-info');
    desc.append(
      el('strong', '', formatAdminDate(d.day) + ` (${d.day})`),
      el('span', '', d.reason ? ' · ' + d.reason : ' · Studio closed')
    );
    const button = el('button', 'btn ghost', 'Unblock');
    button.type = 'button';
    button.addEventListener('click', async () => {
      try {
        await api('/api/admin/blocked-days/' + d.day, 'DELETE');
        await load();
        alertUser(`Unblocked ${d.day}.`, true);
      } catch (e) {
        alertUser(e.message);
      }
    });
    item.append(desc, button);
    target.append(item);
  });
}

function renderServices(services) {
  const target = $('admin-services');
  target.replaceChildren();
  if (!services.length) {
    target.append(el('p', 'hint', 'No services configured.'));
    return;
  }
  services.forEach(s => {
    const row = el('div', 'admin-service-item');
    const left = el('div', 'admin-service-meta');
    left.append(
      el('span', 'ref-badge', `#${s.id}`),
      el('strong', '', s.name)
    );
    const right = el('div', 'admin-service-badges');
    right.append(
      el('span', 'duration-pill', s.duration_minutes + ' minutes'),
      el('span', 'status', 'Active')
    );
    row.append(left, right);
    target.append(row);
  });
}

function renderSchedule(schedule) {
  const target = $('hours-rows');
  target.replaceChildren();
  schedule.forEach(day => {
    const row = el('div', 'hours-row' + (day.is_open ? ' is-open' : ' is-closed'));
    row.dataset.weekday = day.weekday;

    const dayLabel = el('span', 'day-name', names[day.weekday]);

    const toggleWrap = el('label', 'toggle-label');
    const box = el('input');
    box.type = 'checkbox';
    box.checked = !!day.is_open;
    box.setAttribute('aria-label', 'Open on ' + names[day.weekday]);
    const toggleText = el('span', 'toggle-state-text', day.is_open ? 'Open' : 'Closed');
    toggleWrap.append(box, toggleText);

    const start = el('input');
    start.type = 'time';
    start.step = '1800';
    start.value = day.open_time;
    start.disabled = !day.is_open;
    start.setAttribute('aria-label', names[day.weekday] + ' opening time');

    const end = el('input');
    end.type = 'time';
    end.step = '1800';
    end.value = day.close_time;
    end.disabled = !day.is_open;
    end.setAttribute('aria-label', names[day.weekday] + ' closing time');

    box.addEventListener('change', () => {
      const open = box.checked;
      row.classList.toggle('is-open', open);
      row.classList.toggle('is-closed', !open);
      toggleText.textContent = open ? 'Open' : 'Closed';
      start.disabled = !open;
      end.disabled = !open;
    });

    row.append(dayLabel, toggleWrap, start, end);
    target.append(row);
  });
}

// Event Listeners
$('login-form').addEventListener('submit', e => {
  e.preventDefault();
  token = $('token').value.trim();
  sessionStorage.setItem('wingscraft_admin_key', token);
  load();
});

$('logout').addEventListener('click', () => logout());
$('refresh').addEventListener('click', () => load());

document.querySelectorAll('.tab').forEach(button =>
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', button === b));
    ['bookings', 'settings', 'services'].forEach(
      id => ($('panel-' + id).hidden = id !== button.dataset.target)
    );
  })
);

// Reservation Filters
$('filter-search')?.addEventListener('input', e => {
  adminState.filterSearch = e.target.value;
  renderBookings();
});

$('filter-date')?.addEventListener('change', e => {
  adminState.filterDate = e.target.value;
  if (adminState.filterDate) {
    adminState.datePreset = 'custom';
  } else {
    adminState.datePreset = 'all';
  }
  renderBookings();
});

$('filter-status')?.addEventListener('change', e => {
  adminState.filterStatus = e.target.value;
  renderBookings();
});

document.querySelectorAll('[data-date-preset]').forEach(btn => {
  btn.addEventListener('click', () => {
    adminState.datePreset = btn.dataset.datePreset;
    adminState.filterDate = '';
    if ($('filter-date')) $('filter-date').value = '';
    renderBookings();
  });
});

$('clear-filters')?.addEventListener('click', () => {
  adminState.filterSearch = '';
  adminState.filterDate = '';
  adminState.filterStatus = 'all';
  adminState.datePreset = 'all';
  if ($('filter-search')) $('filter-search').value = '';
  if ($('filter-date')) $('filter-date').value = '';
  if ($('filter-status')) $('filter-status').value = 'all';
  renderBookings();
});

$('service-form').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await api('/api/admin/services', 'POST', {
      name: $('new-service').value.trim(),
      duration_minutes: Number($('duration').value)
    });
    $('new-service').value = '';
    await load();
    alertUser('Service added.', true);
  } catch (err) {
    alertUser(err.message);
  }
});

$('block-form').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await api('/api/admin/blocked-days', 'POST', {
      date: $('block-date').value,
      reason: $('block-reason').value.trim()
    });
    $('block-form').reset();
    await load();
    alertUser('Date blocked.', true);
  } catch (err) {
    alertUser(err.message);
  }
});

$('hours-form').addEventListener('submit', async e => {
  e.preventDefault();
  const schedule = [...document.querySelectorAll('.hours-row')].map(r => {
    const inputs = r.querySelectorAll('input');
    return {
      weekday: Number(r.dataset.weekday),
      is_open: inputs[0].checked,
      open_time: inputs[1].value,
      close_time: inputs[2].value
    };
  });
  try {
    await api('/api/admin/schedule', 'PUT', { schedule });
    await load();
    alertUser('Opening hours saved.', true);
  } catch (err) {
    alertUser(err.message);
  }
});

if (token) load();
