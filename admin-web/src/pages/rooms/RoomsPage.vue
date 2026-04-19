<template>
  <div>
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索会议室名称" clearable style="width:220px" @change="loadRooms" />
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width:120px;margin-left:8px" @change="loadRooms">
        <el-option label="启用" :value="1" />
        <el-option label="停用" :value="0" />
      </el-select>
      <el-button type="primary" style="margin-left:auto" @click="openForm(null)">新增会议室</el-button>
    </div>

    <el-table :data="rooms" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="location" label="位置" />
      <el-table-column prop="capacity" label="容量" width="80" />
      <el-table-column prop="facilities" label="设施" show-overflow-tooltip />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button text type="primary" @click="openForm(row)">编辑</el-button>
          <el-button text type="warning" @click="openPermissions(row)">授权</el-button>
          <el-button text type="danger" @click="handleDelete(row)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      :page-size="20"
      :total="total"
      layout="total, prev, pager, next"
      class="pagination"
      @current-change="loadRooms"
    />

    <!-- Room form dialog -->
    <el-dialog v-model="formVisible" :title="editRoom ? '编辑会议室' : '新增会议室'" width="500px">
      <el-form :model="formData" label-width="80px">
        <el-form-item label="名称" required><el-input v-model="formData.name" /></el-form-item>
        <el-form-item label="位置"><el-input v-model="formData.location" /></el-form-item>
        <el-form-item label="容量"><el-input-number v-model="formData.capacity" :min="1" /></el-form-item>
        <el-form-item label="设施"><el-input v-model="formData.facilities" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="formData.description" type="textarea" /></el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="formData.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRoom">保存</el-button>
      </template>
    </el-dialog>

    <!-- Permissions drawer -->
    <PermissionsDrawer
      v-if="permRoom"
      v-model="permDrawerVisible"
      :room="permRoom"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listRooms, createRoom, updateRoom, deleteRoom, type Room } from '@/api/rooms'
import PermissionsDrawer from './PermissionsDrawer.vue'

const rooms = ref<Room[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const statusFilter = ref<number | undefined>(undefined)
const loading = ref(false)

const formVisible = ref(false)
const saving = ref(false)
const editRoom = ref<Room | null>(null)
const formData = reactive<Partial<Room>>({
  name: '', location: '', capacity: undefined,
  facilities: '', description: '', status: 1,
})

const permDrawerVisible = ref(false)
const permRoom = ref<Room | null>(null)

onMounted(loadRooms)

async function loadRooms() {
  loading.value = true
  try {
    const res = await listRooms({
      keyword: keyword.value || undefined,
      status: statusFilter.value,
      page: page.value,
    })
    rooms.value = res.list
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openForm(room: Room | null) {
  editRoom.value = room
  if (room) {
    Object.assign(formData, room)
  } else {
    Object.assign(formData, { name: '', location: '', capacity: undefined, facilities: '', description: '', status: 1 })
  }
  formVisible.value = true
}

async function saveRoom() {
  saving.value = true
  try {
    if (editRoom.value) {
      await updateRoom(editRoom.value.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createRoom(formData)
      ElMessage.success('创建成功')
    }
    formVisible.value = false
    loadRooms()
  } finally {
    saving.value = false
  }
}

async function handleDelete(room: Room) {
  await ElMessageBox.confirm(`确认停用会议室「${room.name}」？`, '提示', { type: 'warning' })
  await deleteRoom(room.id)
  ElMessage.success('已停用')
  loadRooms()
}

function openPermissions(room: Room) {
  permRoom.value = room
  permDrawerVisible.value = true
}
</script>

<style scoped>
.toolbar { display: flex; align-items: center; margin-bottom: 16px; }
.pagination { margin-top: 16px; justify-content: flex-end; }
</style>
