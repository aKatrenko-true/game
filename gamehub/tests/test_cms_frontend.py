from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def test_cms_visibility_is_applied_to_desktop_mobile_navigation_and_ctas():
    public_script = (STATIC / "cms-public.js").read_text(encoding="utf-8")
    app_script = (STATIC / "app.js").read_text(encoding="utf-8")

    # The same hidden-view state is shared with the SPA renderer.
    assert 'window.__cmsHiddenViews=hiddenViews' in public_script
    assert 'window.__cmsHiddenViews?.has(v)' in app_script
    assert '[data-view="'+ '" + view + "' + '"],[data-go="'+ '" + view + "' + '"]' in public_script
    assert 'window.render("overview")' in public_script


def test_cms_public_content_is_inserted_as_text_not_executable_html():
    public_script = (STATIC / "cms-public.js").read_text(encoding="utf-8")
    assert 'h.textContent=s.title' in public_script
    assert 'p.textContent=s.body' in public_script
    assert 'img.alt=s.title' in public_script
    assert 'el.innerHTML' not in public_script


def test_homepage_includes_cms_script_and_both_navigation_layouts():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'src="/static/cms-public.js' in html
    assert 'class="mobile-nav"' in html
    assert 'class="sidebar"' in html
    for view in ("players", "teams", "matches"):
        assert f'data-view="{view}"' in html


def test_cms_editor_exposes_sections_appearance_and_media_workflows():
    editor = (STATIC / "cms.js").read_text(encoding="utf-8")
    assert 'data-cms-tab' in editor
    assert 'renderSections()' in editor
    assert 'renderAppearance()' in editor
    assert 'renderMedia()' in editor
    assert '1.5*1024*1024' in editor
