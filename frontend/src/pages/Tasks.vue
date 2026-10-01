<template>
  <div>
    <h1 class="brand">任务</h1>
    <p class="muted">权重决定每周占格数：权重 N 的 clean 任务每天占 N 格。改权重只影响之后新生成的周。</p>
    <form @submit.prevent="add">
      <input v-model="title" placeholder="任务名" />
      <button type="submit">添加</button>
    </form>
    <p v-if="err" class="err">{{ err }}</p>
    <ul class="list">
      <li v-for="t in rows" :key="t.id">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <strong>{{ t.title }}</strong>
          <span class="muted">· {{ t.data_quality }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;margin-top:6px">
          <label class="muted">权重
            <input
              type="number"
              style="width:84px;margin:0 0 0 6px"
              :value="drafts[t.id] ?? t.weight"
              @input="setDraft(t.id, $event.target.value)"
            />
          </label>
          <button type="button" @click="save(t.id)">保存</button>
          <span class="muted">本周快照 {{ snapOf(t.id) }}</span>
        </div>
        <p v-if="dirty(t)" class="err" style="margin:6px 0 0">
          已生成的本周仍按旧权重 {{ snapOf(t.id) }} 占格，重新生成后才按新权重 {{ drafts[t.id] }}。
        </p>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const title = ref('')
const err = ref('')
const drafts = ref({})
const snapshots = ref({})
const weekId = 1
function snapOf(id) { return snapshots.value[id] ?? '—' }
function setDraft(id, v) { drafts.value = { ...drafts.value, [id]: v } }
function dirty(t) {
  const d = drafts.value[t.id]
  return d !== undefined && d !== '' && Number(d) !== Number(snapshots.value[t.id])
}
async function load() {
  err.value = ''
  try {
    rows.value = await api('/tasks')
    const b = await api('/weeks/' + weekId + '/board')
    snapshots.value = Object.fromEntries((b.snapshots || []).map(s => [s.task_id, s.weight]))
    drafts.value = {}
  } catch (e) { err.value = e.message }
}
async function add() {
  if (!title.value.trim()) return
  await api('/tasks', { method: 'POST', body: JSON.stringify({ title: title.value }) })
  title.value = ''; await load()
}
async function save(id) {
  err.value = ''
  const w = Number(drafts.value[id])
  if (!Number.isInteger(w)) { err.value = '权重需为整数'; return }
  try {
    await api('/tasks/' + id, { method: 'PUT', body: JSON.stringify({ weight: w }) })
    await load()
  } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
