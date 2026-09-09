import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Nav from './components/Nav.jsx'
import Home from './pages/Home.jsx'
import Search from './pages/Search.jsx'
import YoutubeUrl from './pages/YoutubeUrl.jsx'
import Article from './pages/Article.jsx'
import History from './pages/History.jsx'

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<Search />} />
        <Route path="/youtube-url" element={<YoutubeUrl />} />
        <Route path="/article/:id" element={<Article />} />
        <Route path="/history" element={<History />} />
        <Route path="*" element={<main className="p-10 text-center text-mute">Page not found.</main>} />
      </Routes>
    </>
  )
}
