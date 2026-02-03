def is_engineer(request):
    if not request.user.is_authenticated:
        return {'is_engineer': False}
    
    # Check session cache first
    is_eng = request.session.get('is_engineer')
    if is_eng is None:
        is_eng = request.user.groups.filter(name='Engineer').exists()
        request.session['is_engineer'] = is_eng
        
    return {'is_engineer': is_eng}
