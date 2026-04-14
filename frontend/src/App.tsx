import { Routes, Route } from 'react-router-dom'
import { Header } from './components/Header'
import { AppGallery } from './pages/AppGallery'
import { AppView } from './pages/AppView'

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<AppGallery />} />
          <Route path="/apps/:appId" element={<AppView />} />
        </Routes>
      </main>
    </div>
  )
}
