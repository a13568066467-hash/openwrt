package router

import (
	"net/http"
	"os"
	"path"
	"path/filepath"
	"strings"

	"github.com/go-chi/chi/v5"
)

func mountUserPortal(r chi.Router, dir string) {
	dir = strings.TrimSpace(dir)
	if dir == "" {
		return
	}
	info, err := os.Stat(dir)
	if err != nil || !info.IsDir() {
		return
	}

	handler := spaHandler(dir)
	r.Handle("/portal", http.RedirectHandler("/portal/", http.StatusFound))
	r.Handle("/portal/*", http.StripPrefix("/portal", handler))
}

func spaHandler(dir string) http.Handler {
	fileServer := http.FileServer(http.Dir(dir))
	index := filepath.Join(dir, "index.html")
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rel := strings.TrimPrefix(path.Clean("/"+r.URL.Path), "/")
		if rel == "" || rel == "." {
			w.Header().Set("Cache-Control", "no-store")
			http.ServeFile(w, r, index)
			return
		}
		target := filepath.Join(dir, filepath.FromSlash(rel))
		if _, err := os.Stat(target); err != nil {
			w.Header().Set("Cache-Control", "no-store")
			http.ServeFile(w, r, index)
			return
		}
		fileServer.ServeHTTP(w, r)
	})
}
