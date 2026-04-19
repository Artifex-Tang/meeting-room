<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openForm(null)">新增部门</el-button>
    </div>

    <el-table :data="depts" v-loading="loading" stripe row-key="id">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="上级部门">
        <template #default="{ row }">{{ parentName(row.parent_id) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button text type="primary" @click="openForm(row)">编辑</el-button>
          <el-button text type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="formVisible" :title="editDept ? '编辑部门' : '新增部门'" width="400px">
      <el-form :model="formData" label-width="80px">
        <el-form-item label="名称" required><el-input v-model="formData.name" /></el-form-item>
        <el-form-item label="上级部门">
          <el-select v-model="formData.parent_id" clearable placeholder="无（顶级）" style="width:100%">
            <el-option
              v-for="d in depts.filter(d => d.id !== editDept?.id)"
              :key="d.id"
              :label="d.name"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDept">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listDepartments, createDepartment, updateDepartment, deleteDepartment, type Department } from '@/api/users'

const depts = ref<Department[]>([])
const loading = ref(false)

const formVisible = ref(false)
const saving = ref(false)
const editDept = ref<Department | null>(null)
const formData = reactive<{ name: string; parent_id: number | null | undefined }>({ name: '', parent_id: undefined })

onMounted(loadDepts)

async function loadDepts() {
  loading.value = true
  try {
    depts.value = await listDepartments()
  } finally {
    loading.value = false
  }
}

function parentName(parentId: number | null) {
  if (!parentId) return '—'
  return depts.value.find(d => d.id === parentId)?.name ?? '—'
}

function openForm(dept: Department | null) {
  editDept.value = dept
  if (dept) {
    Object.assign(formData, { name: dept.name, parent_id: dept.parent_id })
  } else {
    Object.assign(formData, { name: '', parent_id: undefined })
  }
  formVisible.value = true
}

async function saveDept() {
  if (!formData.name.trim()) { ElMessage.warning('请输入部门名称'); return }
  saving.value = true
  try {
    if (editDept.value) {
      await updateDepartment(editDept.value.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createDepartment(formData)
      ElMessage.success('创建成功')
    }
    formVisible.value = false
    loadDepts()
  } finally {
    saving.value = false
  }
}

async function handleDelete(dept: Department) {
  await ElMessageBox.confirm(`确认删除部门「${dept.name}」？该部门下的用户将变为无部门。`, '提示', { type: 'warning' })
  await deleteDepartment(dept.id)
  ElMessage.success('已删除')
  loadDepts()
}
</script>

<style scoped>
.toolbar { display: flex; align-items: center; margin-bottom: 16px; }
</style>
