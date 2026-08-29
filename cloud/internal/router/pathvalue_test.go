package router

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"
)

// Admin handlers read path parameters with r.PathValue, which is a
// net/http ServeMux feature. This pins down whether chi populates it; if it
// does not, every {id} route silently sees an empty string.
func TestChiPopulatesPathValue(t *testing.T) {
	var viaPathValue, viaChi string

	r := chi.NewRouter()
	r.Get("/users/{id}/quota", func(w http.ResponseWriter, req *http.Request) {
		viaPathValue = req.PathValue("id")
		viaChi = chi.URLParam(req, "id")
	})

	req := httptest.NewRequest(http.MethodGet, "/users/42/quota", nil)
	r.ServeHTTP(httptest.NewRecorder(), req)

	if viaChi != "42" {
		t.Fatalf("chi.URLParam returned %q, want \"42\"", viaChi)
	}

	if viaPathValue != "42" {
		t.Fatalf("r.PathValue returned %q under chi routing, so handlers must use "+
			"chi.URLParam instead", viaPathValue)
	}
}
