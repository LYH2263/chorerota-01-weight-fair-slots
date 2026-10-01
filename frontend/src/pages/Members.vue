<template>
  <div>
    <h1 class="brand">成员</h1>
    <form @submit.prevent="add">
      <input v-model="name" placeholder="新成员姓名" />
      <button type="submit">添加</button>
    </form>
    <p v-if="err" class="err">{{ err }}</p>
    <ul class="list">
      <li v-for="m in rows" :key="m.id">
        <strong>{{ m.name }}</strong>
        <span class="muted"> · {{ m.active ? '在岗' : '停用' }} · {{ m.data_quality }}</span>
        <span v-if="m.active && m.data_quality === 'clean'" class="chip coral" style="margin-left:8px">
          本周 {{ loads[m.id] ?? 0 }} 格
        </span>
        <span v-else class="muted" style="margin-left:8px">不参与占格</span>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const name = ref('')
const err = ref('')
const loads = ref({})
const weekId = 1
async function load() {
  err.value = ''
  try {
    rows.value = await api('/members')
    const b = await api('/weeks/' + weekId + '/board')
    loads.value = Object.fromEntries((b.workload || []).map(w => [w.member_id, w.slots]))
  } catch (e) { err.value = e.message }
}
async function add() {
  if (!name.value.trim()) return
  await api('/members', { method: 'POST', body: JSON.stringify({ name: name.value }) })
  name.value = ''; await load()
}
onMounted(load)
</script>
