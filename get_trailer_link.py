import requests
TMDB_API_KEY = '18809516362f6a7593c662860d5177a6'
movie_id = '70574'
url = f'https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}'
res = requests.get(url).json()
videos = res.get('results', [])
for v in videos:
    if v.get('site') == 'YouTube' and v.get('type') == 'Trailer':
        print(f"https://www.youtube.com/watch?v={v.get('key')}")
        break
