import React, { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { createCustomField, fetchCustomFields } from '../lib/customFieldsApi'

const emptyForm = { entity_type: 'JOB', field_name: '', field_type: 'TEXT', options: '' }

export default function SettingsPage() {
  const [fields, setFields] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  async function loadFields() {
    try {
      setFields(await fetchCustomFields())
    } catch {
      setFields([])
    }
  }

  useEffect(() => {
    loadFields()
  }, [])

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    try {
      await createCustomField({
        entity_type: form.entity_type,
        field_name: form.field_name,
        field_type: form.field_type,
        options_json: form.options ? form.options.split(',').map((item) => item.trim()).filter(Boolean) : [],
      })
      toast.success('Custom field added')
      setForm(emptyForm)
      await loadFields()
    } catch {
      toast.error('Unable to add custom field.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-800 bg-slate-900 p-6">
        <p className="text-[10px] font-black uppercase tracking-[0.28em] text-orange-400">Settings</p>
        <h1 className="mt-3 text-3xl font-black text-white">Custom Fields</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">Add tenant-specific fields for jobs, parts, and customers.</p>
      </section>

      <section className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <form onSubmit={submit} className="rounded-[24px] border border-slate-800 bg-slate-900/70 p-5 space-y-4">
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
            Entity
            <select className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" value={form.entity_type} onChange={(event) => setForm((current) => ({ ...current, entity_type: event.target.value }))}>
              <option value="JOB">Job</option>
              <option value="PART">Part</option>
              <option value="CUSTOMER">Customer</option>
            </select>
          </label>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
            Field name
            <input className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" value={form.field_name} onChange={(event) => setForm((current) => ({ ...current, field_name: event.target.value }))} />
          </label>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
            Type
            <select className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" value={form.field_type} onChange={(event) => setForm((current) => ({ ...current, field_type: event.target.value }))}>
              <option value="TEXT">Text</option>
              <option value="NUMBER">Number</option>
              <option value="DATE">Date</option>
              <option value="DROPDOWN">Dropdown</option>
            </select>
          </label>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
            Dropdown options
            <input className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-white" placeholder="Critical, Rework, Trial" value={form.options} onChange={(event) => setForm((current) => ({ ...current, options: event.target.value }))} />
          </label>
          <button disabled={saving || !form.field_name.trim()} className="w-full rounded-xl bg-orange-500 px-5 py-3 text-sm font-black uppercase tracking-wider text-slate-950 disabled:opacity-60">{saving ? 'Saving...' : 'Add field'}</button>
        </form>

        <div className="rounded-[24px] border border-slate-800 bg-slate-900/70 p-5">
          <h2 className="text-xl font-black text-white">Configured Fields</h2>
          <div className="mt-4 divide-y divide-slate-800">
            {fields.map((field) => (
              <div key={field.field_id} className="flex items-center justify-between gap-3 py-4">
                <div>
                  <div className="font-bold text-white">{field.field_name}</div>
                  <div className="text-xs uppercase tracking-wider text-slate-500">{field.entity_type} | {field.field_type}</div>
                </div>
                <span className="rounded-full bg-slate-950 px-3 py-1 text-xs text-slate-400">{field.options_json?.length || 0} options</span>
              </div>
            ))}
            {fields.length === 0 && <p className="py-8 text-center text-slate-500">No custom fields yet.</p>}
          </div>
        </div>
      </section>
    </div>
  )
}
