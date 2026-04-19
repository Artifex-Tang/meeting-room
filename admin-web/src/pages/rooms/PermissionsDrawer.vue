<template>
  <el-drawer
    :model-value="modelValue"
    :title="`授权管理 — ${room.name}`"
    size="480px"
    @update:model-value="$emit('update:modelValue', $event)"
    @open="load"
  >
    <el-tabs v-model="activeTab">
      <!-- Users tab -->
      <el-tab-pane label="用户授权" name="users">
        <div class="perm-toolbar">
          <el-select
            v-model="selectedUserIds"
            multiple
            filterable
            remote
            :remote-method="searchUsers"
            :loading="userSearching"
            placeholder="搜索用户姓名 / 昵称"
            value-key="id"
            style="flex:1"
          >
            <el-option
              v-for="u in userOptions"
              :key="u.id"
              :label="u.real_name || u.nickname || u.openid"
              :value="u.id"
            />
          </el-select>
          <el-button type="primary" :loading="addingUsers" @click="addUsers" style="margin-left:8px">添加</el-button>
        </div>
        <el-table :data="perms.users" v-loading="loading" stripe>
          <el-table-column label="姓名" :formatter="(r: any) => r.real_name || r.nickname || '—'" />
          <el-table-column prop="openid" label="OpenID" show-overflow-tooltip />
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button text type="danger" @click="removeUser(row.id)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Depts tab -->
      <el-tab-pane label="部门授权" name="depts">
        <div class="perm-toolbar">
          <el-select
            v-model="selectedDeptIds"
            multiple
            placeholder="选择部门"
            style="flex:1"
          >
            <el-option
              v-for="d in allDepts"
              :key="d.id"
              :label="d.name"
              :value="d.id"
            />
          </el-select>
          <el-button type="primary" :loading="addingDepts" @click="addDepts" style="margin-left:8px">添加</el-button>
        </div>
        <el-table :data="perms.depts" v-loading="loading" stripe>
          <el-table-column prop="name" label="部门名称" />
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button text type="danger" @click="removeDept(row.id)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getRoomPermissions, grantUsers, revokeUser, grantDepts, revokeDept,
  type RoomPermissions, type UserSimple, type DeptSimple, type Room,
} from '@/api/rooms'
import { listUsers, listDepartments } from '@/api/users'

const props = defineProps<{ modelValue: boolean; room: Room }>()
const emit = defineEmits(['update:modelValue'])

const activeTab = ref('users')
const loading = ref(false)
const perms = reactive<RoomPermissions>({ users: [], depts: [] })

const userOptions = ref<UserSimple[]>([])
const userSearching = ref(false)
const selectedUserIds = ref<number[]>([])
const addingUsers = ref(false)

const allDepts = ref<DeptSimple[]>([])
const selectedDeptIds = ref<number[]>([])
const addingDepts = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getRoomPermissions(props.room.id)
    perms.users = data.users
    perms.depts = data.depts
  } finally {
    loading.value = false
  }
  const depts = await listDepartments()
  allDepts.value = depts
}

async function searchUsers(query: string) {
  if (!query) return
  userSearching.value = true
  try {
    const res = await listUsers({ keyword: query, status: 1, page_size: 30 })
    userOptions.value = res.list
  } finally {
    userSearching.value = false
  }
}

async function addUsers() {
  if (!selectedUserIds.value.length) return
  addingUsers.value = true
  try {
    await grantUsers(props.room.id, selectedUserIds.value)
    ElMessage.success('授权成功')
    selectedUserIds.value = []
    const data = await getRoomPermissions(props.room.id)
    perms.users = data.users
  } finally {
    addingUsers.value = false
  }
}

async function removeUser(userId: number) {
  await revokeUser(props.room.id, userId)
  perms.users = perms.users.filter(u => u.id !== userId)
  ElMessage.success('已移除')
}

async function addDepts() {
  if (!selectedDeptIds.value.length) return
  addingDepts.value = true
  try {
    await grantDepts(props.room.id, selectedDeptIds.value)
    ElMessage.success('授权成功')
    selectedDeptIds.value = []
    const data = await getRoomPermissions(props.room.id)
    perms.depts = data.depts
  } finally {
    addingDepts.value = false
  }
}

async function removeDept(deptId: number) {
  await revokeDept(props.room.id, deptId)
  perms.depts = perms.depts.filter(d => d.id !== deptId)
  ElMessage.success('已移除')
}
</script>

<style scoped>
.perm-toolbar { display: flex; align-items: center; margin-bottom: 12px; }
</style>
