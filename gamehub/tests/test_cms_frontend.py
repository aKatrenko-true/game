from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def test_cms_visibility_is_applied_to_desktop_mobile_navigation_and_ctas():
    public_script = (STATIC / "cms-public.js").read_text(encoding="utf-8")
    app_script = (STATIC / "app.js").read_text(encoding="utf-8")

    # The same hidden-view state is shared with the SPA renderer.
    assert 'window.__cmsHiddenViews=hiddenViews' in public_script
    assert 'window.__cmsHiddenViews?.has(v)' in app_script
    assert '[data-view="' in public_script and '[data-go="' in public_script
    assert 'window.render("overview")' in public_script
    assert "teamSection=bySlug.teams" in public_script


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

 
def test_admin_password_is_not_persisted_in_browser_storage():
    admin = (STATIC / "admin.js").read_text(encoding="utf-8")
    cms = (STATIC / "cms.js").read_text(encoding="utf-8")
    assert 'sessionStorage.getItem("gh_admin_password")' not in admin
    assert 'sessionStorage.setItem("gh_admin_password"' not in admin
    assert 'sessionStorage.getItem("gh_admin_password")' not in cms
    assert 'sessionStorage.setItem("gh_admin_password"' not in cms

def test_game_card_images_are_editable_in_media_library_and_publicly_applied():
    editor = (STATIC / "cms.js").read_text(encoding="utf-8")
    public_script = (STATIC / "cms-public.js").read_text(encoding="utf-8")
    for key in ("game_cs2_image", "game_valorant_image", "game_wd_image", "game_apex_image"):
        assert key in editor and key in public_script
    assert 'JSON.stringify({image_url:dataUrl})' in editor


def test_cms_image_urls_are_validated_before_css_background_interpolation():
    public_script = (STATIC / "cms-public.js").read_text(encoding="utf-8")
    assert "const safeImageUrl=value=>" in public_script
    assert 'if(tile&&safeImage)' in public_script
    assert "const heroImage=safeImageUrl(hero.image_url)" in public_script
    assert """url("'+safeImage+'")""" in public_script
    assert 'hero.image_url.replace(/"/g' not in public_script
