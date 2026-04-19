<template>
  <div class="login-wrapper">
    <el-card class="login-card">
      <h2>会议室管理后台</h2>
      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" style="width:100%" @click="handleLogin">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { adminLogin } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }],
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const data = await adminLogin(form.username, form.password)
    auth.setAuth(data.token, data.admin)
    ElMessage.success('登录成功')
    router.push(data.admin.must_change_password ? '/profile' : '/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background: #f0f2f5;
}
.login-card { width: 360px; }
h2 { text-align: center; margin-bottom: 24px; }
</style>
