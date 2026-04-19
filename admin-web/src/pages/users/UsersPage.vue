<template>
  <div>
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索姓名 / 昵称" clearable style="width:220px" @change="loadUsers" />
      <el-select v-model="deptFilter" placeholder="部门" clearable style="width:140px;margin-left:8px" @change="loadUsers">
        <el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" />
      </el-select>
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width:100px;margin-left:8px" @change="loadUsers">
        <el-option label="正常" :value="1" />
        <el-option label="禁用" :value="0" />
      </el-select>
    </div>

    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="姓名">
        <template #default="{ row }">{{ row.real_name || row.nickname || '—' }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="手机" width="130" />
      <el-table-column label="部门">
        <template #default="{ row }">{{ deptName(row.dept_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status ? 'success' : 'danger'">{{ row.status ? '正常' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="20"
      :total="total"
      layout="total, prev, pager, next"
      class="pagination"
      @current-change="loadUsers"
    />

    <el-dialog v-model="formVisible" title="编辑用户" width="400px">
      <el-form :model="formData" label-width="80px">
        <el-form-item label="真实姓名"><el-input v-model="formData.real_name" /></el-form-item>
        <el-form-item label="部门">
          <el-select v-model="formData.dept_id" clearable placeholder="无" style="width:100%">
            <el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="formData.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listUsers, updateUser, listDepartments, type User, type Department } from '@/api/users'

const users = ref<User[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const deptFilter = ref<number | undefined>(undefined)
const statusFilter = ref<number | undefined>(undefined)
const loading = ref(false)
const depts = ref<Department[]>([])

const formVisible = ref(false)
const saving = ref(false)
const editUser = ref<User | null>(null)
const formData = reactive<{ real_name: string; dept_id: number | null | undefined; status: number }>({
  real_name: '', dept_id: undefined, status: 1,
})

onMounted(async () => {
  depts.value = await listDepartments()
  await loadUsers()
})

async function loadUsers() {
  loading.value = true
  try {
    const res = await listUsers({
      keyword: keyword.value || undefined,
      dept_id: deptFilter.value,
      status: statusFilter.value,
      page: page.value,
    })
    users.value = res.list
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function deptName(deptId: number | null) {
  if (!deptId) return '—'
  return depts.value.find(d => d.id === deptId)?.name ?? '—'
}

function openEdit(user: User) {
  editUser.value = user
  Object.assign(formData, { real_name: user.real_name || '', dept_id: user.dept_id, status: user.status })
  formVisible.value = true
}

async function saveUser() {
  if (!editUser.value) return
  saving.value = true
  try {
    await updateUser(editUser.value.id, {
      ...formData,
      dept_id: formData.dept_id ?? undefined,
    })
    ElMessage.success('更新成功')
    formVisible.value = false
    loadUsers()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.toolbar { display: flex; align-items: center; margin-bottom: 16px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
</style>
