import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => {
    const data = res.data
    if (data.code === 0) return data.data
    ElMessage.error(data.message || '请求失败')
    return Promise.reject(new Error(data.message))
  },
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('admin_token')
      router.push('/login')
    } else {
      ElMessage.error(err.response?.data?.message || '网络错误')
    }
    return Promise.reject(err)
  },
)

export default http
