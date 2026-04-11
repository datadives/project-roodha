import { useEffect, useMemo, useState } from 'react'
import { toast } from 'react-hot-toast'
import { fetchNotifications, markNotificationRead } from '../lib/notificationsApi'

function formatTimestamp(value) {
  if (!value) return 'Unknown time'

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function prettifyType(value) {
  if (!value) return 'General'

  return value
    .toString()
    .replace(/_/g, ' ')
    .toLowerCase()
    .split(' ')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function unreadBadgeClass(isRead) {
  return isRead
    ? 'bg-slate-100 text-slate-500'
    : 'bg-amber-100 text-amber-700'
}

export default function NotificationsPage() {
  const [loading, setLoading] = useState(true)
  const [markingId, setMarkingId] = useState('')
  const [showUnreadOnly, setShowUnreadOnly] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  async function loadNotifications(unreadOnly = showUnreadOnly) {
    setLoading(true)
    try {
      const response = await fetchNotifications({ unread_only: unreadOnly })
      setNotifications(response.notifications || [])
      setUnreadCount(response.unread_count || 0)
    } catch {
      setNotifications([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadNotifications(showUnreadOnly)
  }, [showUnreadOnly])

  const readCount = useMemo(
    () => notifications.filter((notification) => notification.is_read).length,
    [notifications],
  )

  async function handleMarkRead(notificationId) {
    setMarkingId(notificationId)
    try {
      await markNotificationRead(notificationId)
      toast.success('Notification marked as read')
      await loadNotifications(showUnreadOnly)
      window.dispatchEvent(new CustomEvent('notifications:refresh'))
    } catch {
      // Toasts are already handled by the shared API layer.
    } finally {
      setMarkingId('')
    }
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[32px] border border-white/80 bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.18),transparent_28%),radial-gradient(circle_at_84%_16%,_rgba(14,165,233,0.2),transparent_24%),linear-gradient(135deg,rgba(255,255,255,0.95),rgba(248,250,252,0.92))] p-6 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
        <div className="absolute -right-8 top-10 h-28 w-28 rounded-full bg-amber-200/40 blur-3xl" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Alerts & Updates</p>
            <h1 className="mt-3 text-4xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Notifications center
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              Review tenant broadcasts and personal factory alerts, then acknowledge them directly from one inbox.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-full border border-white/70 bg-white/80 px-4 py-2 text-sm font-semibold text-slate-700">
              Unread: {unreadCount}
            </div>
            <div className="rounded-full border border-white/70 bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
              Read: {readCount}
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-[30px] border border-white/70 bg-white/88 p-6 shadow-[0_20px_55px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Inbox</p>
            <h2 className="mt-2 text-3xl font-semibold text-slate-900" style={{ fontFamily: 'var(--font-display)' }}>
              Factory alerts
            </h2>
          </div>
          <button
            type="button"
            onClick={() => setShowUnreadOnly((current) => !current)}
            className={`rounded-full px-5 py-2.5 text-sm font-semibold transition ${
              showUnreadOnly
                ? 'bg-slate-900 text-white'
                : 'border border-slate-200 bg-white text-slate-600'
            }`}
          >
            {showUnreadOnly ? 'Showing unread only' : 'Show unread only'}
          </button>
        </div>

        {loading ? (
          <div className="mt-6 rounded-[24px] border border-slate-100 bg-slate-50 p-6 text-sm text-slate-500">
            Loading notifications...
          </div>
        ) : notifications.length > 0 ? (
          <div className="mt-6 space-y-4">
            {notifications.map((notification) => (
              <article
                key={notification.notification_id}
                className={`rounded-[26px] border p-5 transition ${
                  notification.is_read
                    ? 'border-slate-200 bg-slate-50/80'
                    : 'border-amber-200 bg-amber-50/60 shadow-[0_12px_30px_rgba(251,191,36,0.08)]'
                }`}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-white">
                        {prettifyType(notification.type)}
                      </span>
                      <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${unreadBadgeClass(notification.is_read)}`}>
                        {notification.is_read ? 'Read' : 'Unread'}
                      </span>
                    </div>
                    <p className="text-base leading-7 text-slate-800">{notification.message}</p>
                    <div className="flex flex-wrap gap-4 text-xs uppercase tracking-[0.16em] text-slate-500">
                      <span>{formatTimestamp(notification.created_at)}</span>
                      <span>{notification.user_id ? 'Personal' : 'Broadcast'}</span>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-3">
                    {!notification.is_read ? (
                      <button
                        type="button"
                        onClick={() => handleMarkRead(notification.notification_id)}
                        disabled={markingId === notification.notification_id}
                        className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {markingId === notification.notification_id ? 'Marking...' : 'Mark as read'}
                      </button>
                    ) : (
                      <div className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-500">
                        Acknowledged
                      </div>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="mt-6 rounded-[24px] border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm leading-6 text-slate-500">
            {showUnreadOnly
              ? 'No unread notifications right now. Your inbox is clear.'
              : 'No notifications have been generated for this tenant yet.'}
          </div>
        )}
      </section>
    </div>
  )
}
