import { useRouter } from 'next/router'
import useSWR from 'swr'
const fetcher = (u)=> fetch(u).then(r=>r.json())

export default function Track(){
  const router = useRouter()
  const { id } = router.query
  const { data } = useSWR(id ? `/api/track/${id}` : null, fetcher)
  const d = data?.details
  return (
    <div className="track-page dark">
      <a href="/">← Geri</a>
      {!d ? <p>Yükleniyor...</p> :
        <div className="hero">
          <img src={d.thumbnail} width="544" height="544" alt="cover" />
          <div className="info">
            <h1>{d.title}</h1>
            <p>{d.author}</p>
            <p>{d.publishDate} • {d.viewCount} izlenme</p>
            <p>{d.shortDescription}</p>
          </div>
        </div>
      }
    </div>
  )
}