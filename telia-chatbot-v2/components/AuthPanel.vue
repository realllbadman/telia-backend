<template>
  <section class="auth-card">
    <div class="title-row">
      <div>
        <p class="eyebrow">Session</p>
        <h2 v-if="isAuthenticated">Signed in</h2>
        <h2 v-else>Sign in to continue</h2>
      </div>

      <span v-if="isAuthenticated" class="badge">Active</span>
    </div>

    <p v-if="isAuthenticated" class="meta">
      {{ user?.username }} <span v-if="user?.email">({{ user.email }})</span>
    </p>

    <p v-if="isAuthenticated && sessionLabel" class="meta">{{ sessionLabel }}</p>

    <form v-if="!isAuthenticated" class="form" @submit.prevent="onSubmit">
      <input
        v-model="identifier"
        type="text"
        placeholder="Email or username"
        :disabled="loading"
        required
      />
      <input
        v-model="password"
        type="password"
        placeholder="Password"
        :disabled="loading"
        required
      />
      <button type="submit" :disabled="loading">
        {{ loading ? 'Signing in...' : 'Sign in' }}
      </button>
    </form>

    <div v-else class="signed-actions">
      <button type="button" class="ghost" @click="$emit('logout')">Sign out</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  isAuthenticated: {
    type: Boolean,
    default: false
  },
  user: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  sessionLabel: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['login', 'logout'])
const identifier = ref('')
const password = ref('')

const onSubmit = () => {
  emit('login', {
    identifier: identifier.value,
    password: password.value
  })
}

watch(
  () => props.isAuthenticated,
  (authenticated) => {
    if (authenticated) {
      password.value = ''
    }
  }
)
</script>

<style scoped>
.auth-card {
  margin-top: 1rem;
  border: 1px solid #293a53;
  border-radius: 16px;
  padding: 1rem;
  background: linear-gradient(180deg, #0d1728 0%, #111d31 100%);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.32);
}

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
}

.eyebrow {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #5eead4;
  font-weight: 700;
}

h2 {
  margin: 0.2rem 0 0;
  font-size: 1.05rem;
  color: #e8f0fb;
}

.badge {
  background: #052e16;
  color: #bbf7d0;
  border: 1px solid #166534;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  font-size: 0.76rem;
  font-weight: 700;
}

.meta {
  margin: 0.5rem 0 0;
  color: #99afc7;
  font-size: 0.9rem;
}

.form {
  margin-top: 0.8rem;
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 0.5rem;
}

input {
  border: 1px solid #33475f;
  border-radius: 10px;
  padding: 0.62rem;
  background: #0b1220;
  color: #e8f0fb;
}

input::placeholder {
  color: #7d93aa;
}

input:focus {
  outline: none;
  border-color: #0ea5a4;
  box-shadow: 0 0 0 3px rgba(14, 165, 164, 0.22);
}

button {
  border: none;
  border-radius: 10px;
  padding: 0.62rem 0.9rem;
  background: linear-gradient(135deg, #0f766e 0%, #0891b2 100%);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.signed-actions {
  margin-top: 0.7rem;
}

.ghost {
  background: #1e293b;
  color: #c7d2fe;
}

.error {
  margin: 0.55rem 0 0;
  color: #fca5a5;
  font-size: 0.9rem;
}

@media (max-width: 900px) {
  .form {
    grid-template-columns: 1fr;
  }
}
</style>
