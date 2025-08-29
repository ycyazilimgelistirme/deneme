import useSWR from 'swr'
import { useState, useEffect } from 'react'
const fetcher = (url) => fetch(url).then(r=>r.json())

export default function Home(){
  const [q, setQ] = useState('');
  const { data: cfg } = useSWR('/api/config', fetcher);
  const [results, setResults] = useState([]);

  async function doSearch(){
    if(!q) return;
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=36`)
    const j = await res.json();
    setResults(j.items || []);
  }

  return (
    <div className="app dark">
      <aside className="sidebar">
        <div className="brand">YCMuzic <span className="pro">Pro</span></div>
      </aside>
      <main className="main">
        <header className="topbar">
          <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Şarkı, sanatçı ara..." />
          <button onClick={doSearch}>Ara</button>
        </header>
        <section className="results">
          {results.length===0 ? <p>Arama yapınız</p> :
            <div className="grid">{results.map(r=> (
              <div key={r.videoId} className="card" onClick={()=> window.location.href=`/track/${r.videoId}`}>
                <img src={r.thumbnail} alt="cover" loading="lazy" />
                <div className="meta"><strong>{r.title}</strong><div className="muted">{r.artists}</div></div>
              </div>
            ))}</div>
          }
        </section>
      </main>
    </div>
  )
}