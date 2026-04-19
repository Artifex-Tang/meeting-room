<template>
  <el-container class="layout-wrapper">
    <el-aside width="200px" class="aside">
      <div class="logo">会议室管理</div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#1d1f23"
        text-color="#ccc"
        active-text-color="#409eff"
      >
        <el-menu-item index="/dashboard"><el-icon><DataLine /></el-icon>总览</el-menu-item>
        <el-menu-item index="/rooms"><el-icon><OfficeBuilding /></el-icon>会议室</el-menu-item>
        <el-menu-item index="/users"><el-icon><User /></el-icon>用户</el-menu-item>
        <el-menu-item index="/departments"><el-icon><Folder /></el-icon>部门</el-menu-item>
        <el-menu-item index="/bookings"><el-icon><Calendar /></el-icon>预订管理</el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon>系统参数</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span v-if="auth.mustChangePassword" class="warn-banner">
          ⚠️ 请先修改初始密码后再操作
        </span>
        <el-dropdown @command="handleCommand" class="user-dropdown">
          <span class="user-info">
            {{ auth.admin?.real_name || auth.admin?.username }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">修改密码</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (cmd === 'profile') {
    router.push('/profile')
  }
}
</script>

<style scoped>
.layout-wrapper { height: 100vh; }
.aside { background: #1d1f23; }
.logo { color: #fff; text-align: center; padding: 20px 0; font-size: 16px; font-weight: bold; }
.header {
  display: flex; align-items: center; justify-content: flex-end;
  background: #fff; border-bottom: 1px solid #e4e7ed; padding: 0 20px;
}
.warn-banner { color: #e6a23c; margin-right: auto; font-size: 13px; }
.user-info { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.user-dropdown { margin-left: auto; }
</style>
